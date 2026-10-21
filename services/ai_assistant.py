import logging
import base64
import json
import re
import requests
from config import settings
from database import get_setting

logger = logging.getLogger(__name__)

# Eng tezkor, barqaror va yuqori kvotali Gemini modellar
PRIMARY_MODEL = "gemini-flash-latest"
FALLBACK_MODEL = "gemini-flash-lite-latest"
THIRD_MODEL = "gemini-3.1-flash-lite"
AUDIO_PRIMARY_MODEL = "gemini-flash-latest"
AUDIO_FALLBACK_MODEL = "gemini-flash-lite-latest"

def detect_message_language(text: str) -> str:
    """
    Xabar qaysi tilda yozilganini aniqlash:
    Qaytaradi: 'en' (Ingliz tili), 'ru' (Rus tili) yoki 'uz' (O'zbek tili)
    """
    if not text:
        return "uz"
    t = text.lower().strip()

    # 1. Rus tili tekshiruvi (Kirill va ruscha kalit so'zlar)
    ru_markers = [
        "сколько", "стоит", "цена", "обучение", "курс", "курсы", "здравствуйте",
        "привет", "добрый", "день", "вечер", "можно", "информация", "расскажите",
        "подробнее", "хочу", "поступить", "где", "когда", "стоимость", "учеба",
        "какие", "направления", "адрес", "номер", "телефон", "пожалуйста", "спасибо",
        "скажите", "программа", "условия", "поступления", "прием", "платно", "скидка",
        "сертификат", "диплом", "модуль", "модули"
    ]
    if any(w in t for w in ru_markers) or any(c in t for c in ['ы', 'щ', 'ъ', 'ь', 'ц', 'ё']):
        return "ru"
    if len(re.findall(r"[\u0400-\u04FF]", t)) >= 3:
        uz_cyrillic = ["катнаш", "керак", "нарх", "качон", "салом", "рахмат", "укув", "модул"]
        if not any(k in t for k in uz_cyrillic):
            return "ru"

    # 2. Ingliz tili tekshiruvi (So'z chegaralari bilan xatosiz qidirish)
    en_patterns = [
        r"\b(?:hello|hi|hey|good\s+(?:morning|afternoon|evening))\b",
        r"\b(?:how\s+much|cost|price|tuition|fees?)\b",
        r"\b(?:training|courses?|program(?:me)?s?|admission|apply|register|registration)\b",
        r"\b(?:hotel|tourism|hospitality|management)\b",
        r"\b(?:information|details|requirements|schedule)\b",
        r"\b(?:can\s+i|i\s+want|i\s+would\s+like|tell\s+me|where\s+is|when\s+does)\b",
        r"\b(?:thank\s+you|thanks|please|interested)\b"
    ]
    for pat in en_patterns:
        if re.search(pat, t):
            uz_indicators = [
                r"\bqancha\b", r"\bkerak\b", r"\bbormi\b", r"\bhaqida\b", r"\buchun\b", 
                r"\bsalom\b", r"\bqachon\b", r"\bqatnash\b", r"\bedim\b", r"\bman\b", 
                r"\bsiz\b", r"\biltimos\b", r"\bboladimi\b", r"\bo‘quv\b", r"\bo'quv\b"
            ]
            if not any(re.search(u, t) for u in uz_indicators):
                return "en"

    return "uz"

def is_russian_message(text: str) -> bool:
    return detect_message_language(text) == "ru"

def is_english_message(text: str) -> bool:
    return detect_message_language(text) == "en"

def clean_ai_output(text: str) -> str:
    """
    AI javobidan har qanday ichki fikrlash (thinking) qoldiqlari,
    variantlar ro'yxati yoki markdown sarlavhalarini tozalash
    """
    if not text:
        return ""
    text = text.strip()

    # Qo'shtirnoqlardan tozalash
    if (text.startswith('"') and text.endswith('"')) or (text.startswith('«') and text.endswith('»')):
        text = text[1:-1].strip()

    # Agar model bir nechta variant chiqargan bo'lsa (masalan: **1-variant:**), 1-variant matnini ajratib olish
    if "**1-variant" in text.lower() or "**variant 1" in text.lower() or "1-variant:" in text.lower() or "**вариант 1" in text.lower() or "**option 1" in text.lower():
        lines = text.split("\n")
        cleaned_lines = []
        capture = False
        for line in lines:
            if any(term in line.lower() for term in ["variant", "вариант", "option"]) and ("1" in line or "1-" in line):
                capture = True
                continue
            if capture and any(term in line.lower() for term in ["variant 2", "2-variant", "вариант 2", "option 2", "maslahat"]):
                break
            if capture and line.strip():
                cleaned_lines.append(line.strip().strip('"').strip('«').strip('»'))
        if cleaned_lines:
            text = "\n".join(cleaned_lines)

    # Ichki inglizcha reja yoki thinking sarlavhalarini olib tashlash
    lines = [
        l for l in text.split("\n") 
        if not re.match(r"^\s*[:\*#\-]+\s*[:\*#\-]?\s*(greeting|acknowledg|thought|step|instruction|thinking)", l, re.IGNORECASE)
    ]
    text = "\n".join(lines).strip()

    # Boshidagi keraksiz belgilarni (:**, **, va h.k.) tozalash
    text = re.sub(r"^[:\*#\s\-\.\>\=]+", "", text).strip()

    return text

def generate_ai_reply(user_message: str, client_context: dict, is_first_message: bool = False, chat_history: list = None) -> str | None:
    """
    Google Gemini AI orqali mijoz xabariga professional, do'stona va suhbat tarixini hisobga olgan holda javob yaratish (O'zbek, Rus, Ingliz tillarida)
    """
    if get_setting("ai_enabled", "1") != "1":
        return None

    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    if not api_key:
        logger.info("AI Yordamchi yoqilgan, lekin Gemini API kalit kiritilmagan.")
        return None

    system_prompt = get_setting("ai_system_prompt", "")

    client_name = client_context.get("full_name") or "Hali noma'lum"
    phone_status = "Berilgan" if client_context.get("phone") else "Hali berilmagan"
    campaign = client_context.get("campaign") or "Umumiy ta'lim kurslari"

    # Tilni aniqlash
    lang = detect_message_language(user_message)
    if lang == "uz" and chat_history and len(chat_history) > 1:
        for prev in reversed(chat_history[:-1]):
            if prev.get("role") == "user":
                prev_lang = detect_message_language(prev.get("text", ""))
                if prev_lang in ["ru", "en"]:
                    lang = prev_lang
                    break

    # Salomlashish qoidasi
    if is_first_message:
        if lang == "en":
            greeting_instruction = "This is the client's FIRST message. Greet politely in English (e.g.: «Hello!» or «Welcome!»)."
        elif lang == "ru":
            greeting_instruction = "Это ПЕРВОЕ сообщение клиента. Поздоровайтесь дружелюбно (например: «Здравствуйте!» или «Добрый день!»)."
        else:
            greeting_instruction = "Bu mijozning BIRINCHI xabari. Salomlashish lozim (masalan: «Assalomu alaykum!» deb boshlang)."
    else:
        if lang == "en":
            greeting_instruction = "STRICT RULE: This is an ongoing conversation! You have ALREADY greeted this client before. Do NOT greet again. Answer the question directly."
        elif lang == "ru":
            greeting_instruction = "СТРОГОЕ ПРАВИЛО: Это продолжающийся диалог! Вы УЖЕ здоровались с этим клиентом ранее. НЕ здоровайтесь заново, сразу и прямо отвечайте на вопрос клиента."
        else:
            greeting_instruction = "QAT'IY QOIDA: Bu davom etayotgan muloqot! Siz bu tinglovchi bilan allaqachon salomlashgansiz. HECH QACHON qayta salomlashmang! Salomlashmasdan darhol to'g'ridan-to'g'ri savolga javob bering."

    # Qat'iy til yo'riqnomasi
    if lang == "en":
        lang_rule = (
            "🚨 CRITICAL LANGUAGE RULE: The user wrote in ENGLISH! "
            "Your response MUST be 100% in natural, fluent, professional ENGLISH! Not a single word in Uzbek or Russian! "
            "If the client hasn't provided a phone number yet, politely request contact details in English: "
            "«To send you the detailed curriculum, schedule, and tuition fees, please leave your name and phone number 😊»"
        )
    elif lang == "ru":
        lang_rule = (
            "🚨 КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО ЯЗЫКА: Пользователь написал на РУССКОМ ЯЗЫКЕ! "
            "Ваш ответ ОБЯЗАН быть на 100% НА РУССКОМ ЯЗЫКЕ! Ни одного узбекского слова! "
            "Если клиент еще не оставил номер телефона, в конце ответа вежливо запросите контактные данные на русском: "
            "«Чтобы мы могли отправить вам подробную учебную программу, расписание занятий и актуальную стоимость обучения, пожалуйста, оставьте ваше имя и номер телефона 😊»"
        )
    else:
        lang_rule = (
            "QAT'IY TIL TALABI: Tinglovchi O'ZBEK TILIDA yozdi. Javobingizni o'zbek tilida, muloyim va samimiy bering. "
            "Agar mijoz hali telefon raqamini bermagan bo'lsa, javobingiz oxirida: "
            "«Batafsil o'quv dasturi, qabul shartlari va dars jadvalini sizga yuborishimiz uchun, iltimos, ismingiz va telefon raqamingizni qoldiring 😊» deb muloyimlik bilan raqam so'rang."
        )

    # Suhbat tarixini kontekstga kiritish
    history_section = ""
    if chat_history and len(chat_history) > 1:
        history_lines = []
        for h in chat_history[:-1]:
            r = "Tinglovchi" if h.get("role") == "user" else "Virtual maslahatchi"
            t = (h.get("text") or "").strip()
            if t:
                history_lines.append(f"{r}: {t}")
        if history_lines:
            history_section = (
                f"\n--- AVVALGI SUHBAT TARIXI ---\n"
                + "\n".join(history_lines[-8:])
                + "\n"
            )

    context_prompt = (
        f"{system_prompt}\n\n"
        f"--- HOZIRGI TINGLOVCHI/MIJOZ HAQIDA MA'LUMOT ---\n"
        f"Mijoz ismi: {client_name}\n"
        f"Telefon raqami holati: {phone_status}\n"
        f"Qiziqqan yo'nalishi/aksiyasi: {campaign}\n"
        f"{history_section}\n"
        f"{greeting_instruction}\n"
        f"{lang_rule}\n"
        f"Javobingiz Instagram chatiga mos, qisqa (2-3 jumla), o'ta xushmuomala va samimiy bo'lsin. "
        f"Hech qanday ichki reja yoki sarlavhalarsiz, to'g'ridan-to'g'ri 1 ta yaxlit xabar qaytaring."
    )

    headers = {"Content-Type": "application/json"}

    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL, THIRD_MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        gen_config = {
            "temperature": 0.3,
            "maxOutputTokens": 600
        }
        if "gemini-3" in model_name:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload = {
            "contents": [{"role": "user", "parts": [{"text": user_message}]}],
            "systemInstruction": {"parts": [{"text": context_prompt}]},
            "generationConfig": gen_config
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=8)
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        ai_text = clean_ai_output(parts[0].get("text", ""))
                        if ai_text:
                            logger.info(f"Gemini AI ({model_name}) javob yaratdi: {ai_text[:50]}...")
                            return ai_text
            else:
                logger.warning(f"Gemini API ({model_name}) javob kodi [{response.status_code}]: {response.text[:120]}")

        except Exception as e:
            logger.error(f"AI ({model_name}) so'rovida xatolik: {e}")

    return None

def analyze_lead_need(chat_history: list, client_context: dict) -> str:
    """
    Mijoz nimalarga qiziqqanini va unga aynan nima kerakligini Gemini AI orqali aniqlash.
    Ushbu xulosa Telegram guruhiga yangi lid xabarida va CRM jadvalida ko'rinadi.
    """
    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    campaign = client_context.get("campaign") or "Umumiy ta'lim kurslari"
    last_msg = client_context.get("last_message") or ""
    client_name = client_context.get("full_name") or "Mijoz"

    history_lines = []
    if chat_history and isinstance(chat_history, list):
        for msg in chat_history:
            role = "Tinglovchi" if msg.get("role") == "user" else "Akademiya boti"
            text = msg.get("text", "")
            if text:
                history_lines.append(f"{role}: {text}")
    
    if not history_lines and last_msg:
        history_lines.append(f"Tinglovchi: {last_msg}")

    dialog_str = "\n".join(history_lines) if history_lines else f"So'rov: {last_msg or campaign}"

    if api_key:
        prompt = (
            "Siz Xalqaro Turizm Akademiyasi Samarqand kampusining malakali mijozlar tahlilchisisiz.\n"
            "Quyida Instagram orqali kelgan tinglovchi bilan bo'lgan muloqot berilgan.\n\n"
            f"--- TINGLOVCHI HAQIDA ---\n"
            f"Ismi: {client_name}\n"
            f"Yo'nalishi / Aksiya: {campaign}\n\n"
            f"--- SUHBAT TARIXI ---\n"
            f"{dialog_str}\n\n"
            "VAZIFA: Ushbu tinglovchi aynan qaysi kurs yoki mavzuga qiziqqanini, unga qanday ma'lumotlar kerakligini "
            "(masalan: kurs narxi, o'qish muddati, sertifikat turi, dars vaqtlari, amaliyot yoki qabul shartlari) "
            "va mutaxassislarimiz bog'langanda nimalarga e'tibor qaratishi kerakligini 1-2 ta aniq, tushunarli, "
            "o'zbek tilidagi qisqa jumla bilan xulosa qilib bering.\n"
            "Hech qanday kirish so'z yoki ortiqcha belgilarsiz, faqat xulosa matnini qaytaring."
        )

        headers = {"Content-Type": "application/json"}

        for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            gen_config = {"temperature": 0.2, "maxOutputTokens": 400}
            if "gemini-3" in model_name:
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}

            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": gen_config
            }
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            summary = clean_ai_output(parts[0].get("text", ""))
                            if summary:
                                logger.info(f"AI Lead tahlili ({model_name}): {summary}")
                                return summary
            except Exception as e:
                logger.error(f"AI Lead tahlilida xatolik ({model_name}): {e}")

    # Fallback evristik tahlil
    summary_parts = []
    if campaign and campaign != "Umumiy":
        summary_parts.append(f"{campaign} yo'nalishiga qiziqqan.")
    if last_msg:
        lm_lower = last_msg.lower()
        if any(w in lm_lower for w in ["narx", "qancha", "nechpul", "стоит", "цена", "how much", "cost", "price", "fee"]):
            summary_parts.append("Kurs narxi va to'lov shartlarini so'ragan.")
        elif any(w in lm_lower for w in ["sertifikat", "diplom", "диплом", "certificate"]):
            summary_parts.append("Sertifikat berilishi va maqomi bilan qiziqqan.")
        elif any(w in lm_lower for w in ["vaqt", "boshlan", "jadval", "когда", "schedule", "when"]):
            summary_parts.append("Darslar boshlanish sanasi va vaqti kerak.")
        else:
            summary_parts.append(f"So'rovi: «{last_msg[:60]}»")

    return " ".join(summary_parts) if summary_parts else f"{campaign} bo'yicha to'liq ma'lumot kutyapti."

def generate_ai_comment_dm(comment_text: str, username: str = "", campaign_name: str = "") -> str:
    """
    Instagram post/video ostida izoh qoldirgan tinglovchining Directiga
    AI orqali moslashtirilgan shaxsiy xabar (DM) yaratish (rus, ingliz yoki o'zbek tilida)
    """
    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    system_prompt = get_setting("ai_system_prompt", "")
    user_label = f"@{username}" if username else "tinglovchi"
    lang = detect_message_language(comment_text)

    if api_key and get_setting("ai_enabled", "1") == "1":
        if lang == "en":
            lang_inst = (
                "🚨 LANGUAGE RULE: Comment is in ENGLISH! Your reply MUST be 100% in natural ENGLISH! "
                "Thank them for their interest in our video and kindly ask them to reply with their name "
                "so we can send full program details, schedule, and tuition fees."
            )
        elif lang == "ru":
            lang_inst = (
                "🚨 ПРАВИЛО ЯЗЫКА: Комментарий на РУССКОМ языке! Ваш ответ ОБЯЗАН быть на 100% НА РУССКОМ! "
                "Поблагодарите за проявленный интерес к нашему видео и вежливо попросите написать имя в ответном сообщении, "
                "чтобы отправить подробную программу и условия поступления."
            )
        else:
            lang_inst = (
                "Izoh O'ZBEK tilida! Uning izohidagi e'tibori uchun minnatdorchilik bildirib, "
                "batafsil o'quv dasturi, dars jadvali va narxlarni Directda to'liq taqdim etishimiz uchun ismini yozib qoldirishini so'rang."
            )

        prompt = (
            f"{system_prompt}\n\n"
            f"--- VAZIFA (VIDEO IZOHIGA SHAXSIY DIRECT XABAR) ---\n"
            f"Foydalanuvchi ({user_label}) Instagram videomiz ostida quyidagi izohni qoldirdi:\n"
            f"«{comment_text}»\n"
            f"Video aksiyasi/mavzusi: {campaign_name or 'Umumiy ta''lim'}\n\n"
            f"{lang_inst}\n\n"
            f"QAT'IY QOIDA: Hech qanday 'Variant 1', sarlavha, kirish so'z yoki tushuntirish YOZMANG! "
            f"To'g'ridan-to'g'ri tinglovchiga yuboriladigan 1 dona tayyor xabar matnining o'zini qaytaring."
        )

        headers = {"Content-Type": "application/json"}

        for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            gen_config = {"temperature": 0.3, "maxOutputTokens": 600}
            if "gemini-3" in model_name:
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}

            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": gen_config
            }

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            res_text = clean_ai_output(parts[0].get("text", ""))
                            if res_text:
                                logger.info(f"AI Comment DM yaratdi: {res_text[:50]}...")
                                return res_text
            except Exception as e:
                logger.error(f"AI Comment DM xatosi ({model_name}): {e}")

    # Fallback
    if lang == "en":
        return (
            f"Hello {user_label}! Thank you for your interest in our video. 😊\n\n"
            f"To receive the detailed curriculum, schedule, and admission details, please reply with your name:"
        )
    elif lang == "ru":
        return (
            f"Здравствуйте, {user_label}! Спасибо за интерес к нашему видео. 😊\n\n"
            f"Чтобы мы могли отправить вам подробную учебную программу и условия поступления, пожалуйста, напишите ваше имя:"
        )
    return (
        f"Salom {user_label}! Videomizga bildirgan e'tiboringiz uchun tashakkur. 😊\n\n"
        f"Siz so'ragan batafsil o'quv dasturi va qabul tafsilotlarini yuborishimiz uchun ismingizni yozib qoldiring:"
    )

def generate_ai_followup(chat_history: list, client_context: dict) -> str:
    """
    Suhbati to'xtab qolgan (telefonini bermagan) mijozga samimiy qayta eslatma (Follow-up) yaratish (rus, ingliz yoki o'zbek tilida)
    """
    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    client_name = client_context.get("full_name") or ""
    campaign = client_context.get("campaign") or "Turizm kurslari"

    history_lines = []
    full_text_corpus = ""
    if chat_history and isinstance(chat_history, list):
        for msg in chat_history:
            role = "Tinglovchi" if msg.get("role") == "user" else "Siz"
            text = (msg.get("text") or "").strip()
            if text:
                history_lines.append(f"{role}: {text}")
                full_text_corpus += " " + text

    dialog_str = "\n".join(history_lines[-6:]) if history_lines else f"Qiziqqan kursi: {campaign}"
    lang = detect_message_language(full_text_corpus)
    safe_name = client_name or ("student" if lang == "en" else "клиент" if lang == "ru" else "tinglovchi")

    if api_key and get_setting("ai_enabled", "1") == "1":
        if lang == "en":
            lang_inst = (
                "🚨 LANGUAGE RULE: The conversation is in ENGLISH! Your follow-up reminder MUST be 100% in natural ENGLISH! "
                "Politely offer assistance and invite them to leave their phone number for course details and schedule."
            )
        elif lang == "ru":
            lang_inst = (
                "🚨 ПРАВИЛО ЯЗЫКА: Диалог ведется на РУССКОМ языке! Ваш ответ ОБЯЗАН быть на 100% НА РУССКОМ! "
                "Напишите вежливое, дружелюбное напоминание (1-2 предложения) с предложением продолжить общение и оставить номер телефона "
                "для получения учебной программы."
            )
        else:
            lang_inst = (
                "Ushbu tinglovchiga suhbatni davom ettirish va telefon raqamini so'rash uchun 1-2 jumlali o'ta samimiy, "
                "do'stona va muloyim 1 TA yaxlit eslatma (Follow-up) xabari yozing."
            )

        prompt = (
            "Siz Xalqaro Turizm Akademiyasi Samarqand kampusining g'amxo'r va xushmuomala virtual yordamchisisiz.\n"
            "Tinglovchi Directda muloqot boshlagan, ammo telefon raqamini qoldirmasdan suhbat to'xtab qolgan.\n\n"
            f"--- SUHBAT MAZMUNI ---\n"
            f"Ismi: {safe_name}\n"
            f"Qiziqqan yo'nalishi: {campaign}\n"
            f"{dialog_str}\n\n"
            f"{lang_inst}\n\n"
            "QAT'IY QOIDA: Hech qanday 'Variantlar', sarlavha, izoh yoki tushuntirish yozmang! To'g'ridan-to'g'ri tinglovchiga yuboriladigan xabarning o'zini qaytaring."
        )

        headers = {"Content-Type": "application/json"}

        for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            gen_config = {"temperature": 0.3, "maxOutputTokens": 600}
            if "gemini-3" in model_name:
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}

            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": gen_config
            }

            try:
                response = requests.post(url, json=payload, headers=headers, timeout=8)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            res_text = clean_ai_output(parts[0].get("text", ""))
                            if res_text:
                                logger.info(f"AI Follow-up yaratdi: {res_text[:50]}...")
                                return res_text
            except Exception as e:
                logger.error(f"AI Follow-up xatosi ({model_name}): {e}")

    # Fallback
    if lang == "en":
        return (
            "Hello! You were inquiring about our training programs. "
            "To send you the schedule, fees, and secure your spot, please leave your phone number 😊"
        )
    elif lang == "ru":
        return (
            "Здравствуйте! Вы интересовались нашими программами обучения. "
            "Чтобы мы могли прислать вам расписание занятий и забронировать место, пожалуйста, оставьте ваш номер телефона 😊"
        )
    return (
        f"Salom! Boya {campaign} haqida ma'lumot so'ragan edingiz. "
        f"Dars jadvali va qabul shartlarini yuborishimiz uchun telefon raqamingizni qoldirishga ulgurmadingizmi? Sizga yordam berishdan mamnun bo'lamiz! 😊"
    )

def process_voice_message(audio_bytes: bytes, mime_type: str = "audio/mp4", client_context: dict = None, chat_history: list = None) -> dict | None:
    """
    Gemini Multimodal Audio orqali Instagram Directdagi ovozli xabarni transkripsiya qilish va unga javob qaytarish.
    Qaytaradi lug'at (dict):
    {
        "transcription": "Tinglovchi aytgan gaplar",
        "reply": "AI javob matni",
        "extracted_phone": "Telefon raqami yoki None",
        "extracted_name": "Ismi yoki None",
        "detected_course": "Qiziqqan kursi yoki None",
        "summary": "Qisqa xulosa"
    }
    """
    if get_setting("ai_enabled", "1") != "1":
        return None

    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    if not api_key or not audio_bytes:
        return None

    client_context = client_context or {}
    client_name = client_context.get("full_name") or "Hali noma'lum"
    phone_status = "Berilgan" if client_context.get("phone_number") else "Hali berilmagan"
    campaign = client_context.get("campaign") or "Umumiy ta'lim kurslari"
    system_prompt = get_setting("ai_system_prompt", "")

    history_section = ""
    if chat_history and len(chat_history) > 0:
        history_lines = []
        for h in chat_history[-6:]:
            r = "Tinglovchi" if h.get("role") == "user" else "Siz"
            t = (h.get("text") or "").strip()
            if t:
                history_lines.append(f"{r}: {t}")
        if history_lines:
            history_section = f"\n--- AVVALGI SUHBAT TARIXI ---\n" + "\n".join(history_lines) + "\n"

    audio_prompt = (
        f"{system_prompt}\n\n"
        f"--- HOZIRGI TINGLOVCHI HAQIDA ---\n"
        f"Ismi: {client_name}\n"
        f"Telefon holati: {phone_status}\n"
        f"Yo'nalishi: {campaign}\n"
        f"{history_section}\n\n"
        "MUHIM VAZIFA:\n"
        "1. Ilovadagi audio faylni diqqat bilan tinglang va uning to'liq transkripsiyasini (tinglovchi aytgan barcha so'zlarni) yozing.\n"
        "2. Audioda so'zlashilgan tilni aniqlang: O'zbek, Rus yoki Ingliz tili.\n"
        "3. Tinglovchining savoliga Xalqaro Turizm Akademiyasi koordinatori sifatida qisqa, madaniyatli, do'stona va AYNAN AUDIOLAGI TILDA (100% bir xil tilda) javob bering.\n"
        "4. Agar tinglovchi hali telefon raqamini aytmagan bo'lsa, javobingiz oxirida unga dars jadvali va narxlarni yuborish uchun ism va telefon raqamini so'rang (audio tilida).\n"
        "5. Agar audioda telefon raqami, ismi yoki biron yo'nalish (Gid, Mehmonxona, Restoran, Turoperator va h.k.) aytilgan bo'lsa, ularni ajratib oling.\n\n"
        "JAVOBNI FAQAT VA FAQAT QUYIDAGI TOZA JSON FORMATDA QAYTARING:\n"
        "{\n"
        '  "transcription": "Tinglovchining audio fayldagi so\'zlari",\n'
        '  "reply": "Tinglovchiga yuboriladigan samimiy javob matni",\n'
        '  "extracted_phone": null,\n'
        '  "extracted_name": null,\n'
        '  "detected_course": null,\n'
        '  "summary": "Mijoz maqsadi haqida 1 jumla qisqa xulosa"\n'
        "}\n"
        "Boshqa hech qanday izoh yoki belgi qo'shmang, faqat toza JSON qaytaring."
    )

    try:
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"Audio faylni base64 ga aylantirishda xatolik: {e}")
        return None

    clean_mime = mime_type.split(";")[0].strip() if ";" in mime_type else mime_type.strip()
    if not clean_mime or not clean_mime.startswith("audio/"):
        clean_mime = "audio/mp4"

    headers = {"Content-Type": "application/json"}

    for model_name in [AUDIO_PRIMARY_MODEL, AUDIO_FALLBACK_MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        gen_config = {"temperature": 0.2, "maxOutputTokens": 800}
        if "gemini-3" in model_name:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": audio_prompt},
                        {
                            "inlineData": {
                                "mimeType": clean_mime,
                                "data": audio_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": gen_config
        }

        try:
            res = requests.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        raw_text = clean_ai_output(parts[0].get("text", ""))
                        if "```json" in raw_text:
                            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                        elif "```" in raw_text:
                            raw_text = raw_text.split("```")[1].split("```")[0].strip()

                        try:
                            parsed = json.loads(raw_text)
                            transcript = (parsed.get("transcription") or "").strip()
                            reply = (parsed.get("reply") or "").strip()
                            if transcript or reply:
                                logger.info(f"Ovozli xabar muvaffaqiyatli transkripsiya qilindi: {transcript[:50]}...")
                                return {
                                    "transcription": transcript or "Ovozli xabar",
                                    "reply": reply,
                                    "extracted_phone": parsed.get("extracted_phone"),
                                    "extracted_name": parsed.get("extracted_name"),
                                    "detected_course": parsed.get("detected_course"),
                                    "summary": parsed.get("summary", "")
                                }
                        except Exception as json_err:
                            logger.warning(f"Ovozli xabar JSON tahlil xatosi: {json_err}, xom matn: {raw_text[:80]}")
                            return {
                                "transcription": "Ovozli xabar",
                                "reply": raw_text,
                                "extracted_phone": None,
                                "extracted_name": None,
                                "detected_course": None,
                                "summary": ""
                            }
            else:
                logger.warning(f"Audio Gemini API ({model_name}) javob kodi [{res.status_code}]: {res.text[:120]}")
        except Exception as e:
            logger.error(f"Audio Gemini API ({model_name}) so'rovida xatolik: {e}")

    return None
