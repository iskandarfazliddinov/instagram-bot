import logging
import base64
import json
import re
import requests
from config import settings
from database import get_setting

logger = logging.getLogger(__name__)

# Eng tezkor va yuqori kvotali modellar
PRIMARY_MODEL = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-flash-latest"
AUDIO_PRIMARY_MODEL = "gemini-3-flash-preview"
AUDIO_FALLBACK_MODEL = "gemini-3.5-flash"

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
    if "**1-variant" in text.lower() or "**variant 1" in text.lower() or "1-variant:" in text.lower():
        lines = text.split("\n")
        cleaned_lines = []
        capture = False
        for line in lines:
            if "variant" in line.lower() and ("1" in line or "1-" in line):
                capture = True
                continue
            if capture and ("variant 2" in line.lower() or "2-variant" in line.lower() or "maslahat" in line.lower() or "qaysi birini" in line.lower()):
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
    Google Gemini AI orqali mijoz xabariga professional, do'stona va suhbat tarixini hisobga olgan holda javob yaratish
    """
    if get_setting("ai_enabled", "1") != "1":
        return None

    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    if not api_key:
        logger.info("AI Yordamchi yoqilgan, lekin Gemini API kalit kiritilmagan.")
        return None

    system_prompt = get_setting("ai_system_prompt", "")

    client_name = client_context.get("full_name") or "Hali noma'lum"
    phone_status = client_context.get("phone_number") or "Hali olinmagan"
    campaign = client_context.get("campaign") or "Umumiy"

    if is_first_message:
        greeting_instruction = (
            "SALOMLASHISH QOIDASI: Bu yangi muloqotning birinchi xabari. "
            "Shu sababli xushmuomala salomlashing."
        )
    else:
        greeting_instruction = (
            "QAT'IY QOIDA: Bu davom etayotgan muloqot! Siz bu tinglovchi bilan allaqachon salomlashgansiz. "
            "HECH QACHON xabaringiz boshida «Assalomu alaykum», «Salom» yoki «Vaalaykum assalom» deb qayta salomlashmang! "
            "Salomlashmasdan darhol to'g'ridan-to'g'ri savolga javob bering."
        )

    # Suhbat tarixini kontekstga kiritish
    history_section = ""
    if chat_history and len(chat_history) > 1:
        history_lines = []
        for h in chat_history[:-1]:
            r = "Tinglovchi" if h.get("role") == "user" else "Siz (Virtual maslahatchi)"
            t = (h.get("text") or "").strip()
            if t:
                history_lines.append(f"{r}: {t}")
        if history_lines:
            history_section = (
                f"\n--- AVVALGI SUHBAT TARIXI (Mijozning o'tmishdagi savollari va sizning javoblaringiz) ---\n"
                + "\n".join(history_lines[-10:])
                + "\nESLATMA: Tinglovchining oldingi so'ragan narsalarini eslab qoling. "
                "Agar u avval biror kursni so'ragan bo'lsa, o'sha kontekstni davom ettiring.\n"
            )

    context_prompt = (
        f"{system_prompt}\n\n"
        f"--- HOZIRGI TINGLOVCHI/MIJOZ HAQIDA MA'LUMOT ---\n"
        f"Mijoz ismi: {client_name}\n"
        f"Telefon raqami holati: {phone_status}\n"
        f"Qiziqqan yo'nalishi/aksiyasi: {campaign}\n"
        f"{history_section}\n"
        f"{greeting_instruction}\n"
        f"Eslatma: Tinglovchi qaysi tilda (o'zbek yoki rus) yozgan bo'lsa, xuddi shu tilda ravon, madaniyatli javob bering. "
        f"Agar mijoz hali telefon raqamini bermagan bo'lsa, javobingiz oxirida "
        f"unga batafsil ma'lumot va dars jadvalini yuborish uchun muloyimlik bilan telefon raqamini so'rang. "
        f"Javobingiz Instagram chatiga mos, qisqa (2-3 jumla), o'ta xushmuomala va samimiy bo'lsin. "
        f"Hech qanday ichki reja yoki sarlavhalarsiz, to'g'ridan-to'g'ri 1 ta yaxlit xabar qaytaring."
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_message}]
            }
        ],
        "systemInstruction": {
            "parts": [{"text": context_prompt}]
        },
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 800,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }

    headers = {"Content-Type": "application/json"}

    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()

            if response.status_code == 200:
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        ai_text = clean_ai_output(parts[0].get("text", ""))
                        if ai_text:
                            logger.info(f"Gemini AI ({model_name}) javob yaratdi: {ai_text[:50]}...")
                            return ai_text
            else:
                logger.error(f"Gemini API ({model_name}) xatoligi [{response.status_code}]: {data}")

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

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 400,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }
        headers = {"Content-Type": "application/json"}

        for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)
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
        if "narx" in lm_lower or "qancha" in lm_lower or "nechpul" in lm_lower:
            summary_parts.append("Kurs narxi va to'lov shartlarini so'ragan.")
        elif "sertifikat" in lm_lower or "diplom" in lm_lower:
            summary_parts.append("Sertifikat berilishi va maqomi bilan qiziqqan.")
        elif "vaqt" in lm_lower or "boshlan" in lm_lower or "jadval" in lm_lower:
            summary_parts.append("Darslar boshlanish sanasi va vaqti kerak.")
        else:
            summary_parts.append(f"Murojaati: «{last_msg}».")

    if not summary_parts:
        return f"{campaign} bo'yicha batafsil o'quv dasturi va qabul tafsilotlari kerak."
    return " ".join(summary_parts)

def generate_ai_comment_dm(comment_text: str, username: str = "", campaign_name: str = "") -> str:
    """
    Video/Reels ostida izoh qoldirgan foydalanuvchiga uning izohiga mos aqlli shaxsiy Direct xabar yaratish
    """
    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    system_prompt = get_setting("ai_system_prompt", "")
    user_label = f"@{username}" if username else "tinglovchi"

    if api_key and get_setting("ai_enabled", "1") == "1":
        prompt = (
            f"{system_prompt}\n\n"
            f"--- VAZIFA (VIDEO IZOHIGA SHAXSIY DIRECT XABAR) ---\n"
            f"Foydalanuvchi ({user_label}) Instagram videomiz ostida quyidagi izohni qoldirdi:\n"
            f"«{comment_text}»\n"
            f"Video aksiyasi/mavzusi: {campaign_name or 'Umumiy ta''lim'}\n\n"
            f"Ushbu tinglovchining Instagram Directiga yuboriladigan samimiy, do'stona va professional 1 TA yaxlit xabar yozing (2-3 jumla).\n"
            f"Uning izohidagi e'tibori uchun minnatdorchilik bildirib, batafsil o'quv dasturi, dars jadvali va narxlarni Directda to'liq taqdim etishimiz uchun ismini yozib qoldirishini so'rang.\n\n"
            f"QAT'IY QOIDA: Hech qanday 'Variant 1', 'Variant 2', sarlavha, kirish so'z yoki tushuntirish YOZMANG! "
            f"To'g'ridan-to'g'ri tinglovchiga yuboriladigan 1 dona tayyor xabar matnining o'zini qaytaring."
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 600,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }
        headers = {"Content-Type": "application/json"}

        for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
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
    return (
        f"Salom {user_label}! Videomizga bildirgan e'tiboringiz uchun tashakkur. 😊\n\n"
        f"Siz so'ragan batafsil o'quv dasturi va qabul tafsilotlarini yuborishimiz uchun ismingizni yozib qoldiring:"
    )

def generate_ai_followup(chat_history: list, client_context: dict) -> str:
    """
    Suhbati to'xtab qolgan (telefonini bermagan) mijozga samimiy qayta eslatma (Follow-up) yaratish
    """
    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    client_name = client_context.get("full_name") or ""
    campaign = client_context.get("campaign") or "Turizm kurslari"

    history_lines = []
    if chat_history and isinstance(chat_history, list):
        for msg in chat_history:
            role = "Tinglovchi" if msg.get("role") == "user" else "Siz"
            text = (msg.get("text") or "").strip()
            if text:
                history_lines.append(f"{role}: {text}")

    dialog_str = "\n".join(history_lines[-6:]) if history_lines else f"Qiziqqan kursi: {campaign}"

    safe_name = client_name or "Noma'lum"
    if api_key and get_setting("ai_enabled", "1") == "1":
        prompt = (
            "Siz Xalqaro Turizm Akademiyasi Samarqand kampusining g'amxo'r va xushmuomala virtual yordamchisisiz.\n"
            "Tinglovchi Directda muloqot boshlagan, ammo telefon raqamini qoldirmasdan suhbat to'xtab qolgan.\n\n"
            f"--- SUHBAT MAZMUNI ---\n"
            f"Ismi: {safe_name}\n"
            f"Qiziqqan yo'nalishi: {campaign}\n"
            f"{dialog_str}\n\n"
            "VAZIFA: Ushbu tinglovchiga suhbatni davom ettirish va telefon raqamini so'rash uchun 1-2 jumlali o'ta samimiy, "
            "do'stona va muloyim 1 TA yaxlit eslatma (Follow-up) xabari yozing.\n"
            "QAT'IY QOIDA: Hech qanday 'Variantlar', sarlavha, izoh yoki tushuntirish yozmang! To'g'ridan-to'g'ri tinglovchiga yuboriladigan xabarning o'zini qaytaring."
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 600,
                "thinkingConfig": {"thinkingBudget": 0}
            }
        }
        headers = {"Content-Type": "application/json"}

        for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
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
    name_str = f", {client_name}" if client_name else ""
    return (
        f"Salom{name_str}! 😊 Boya {campaign} bo'yicha ma'lumot so'ragan edingiz. "
        f"Dars jadvali va qabul shartlarini yuborishimiz uchun telefon raqamingizni qoldirishga ulgurmadingizmi? "
        f"Sizga yordam berishdan mamnun bo'lamiz!"
    )

def process_voice_message(audio_bytes: bytes, mime_type: str = "audio/mp4", client_context: dict = None, chat_history: list = None) -> dict | None:
    """
    Google Gemini Multimodal Audio orqali ovozli xabarni (Voice Message):
    1. So'zma-so'z matnga aylantirish (Speech-to-Text / Transkripsiya)
    2. Tinglovchining savoliga mos AI javob yaratish
    3. Agar ovozda ism yoki telefon raqami aytilgan bo'lsa, ularni ajratib olish
    4. Qiziqqan kurs yo'nalishini aniqlash
    """
    if get_setting("ai_enabled", "1") != "1":
        logger.info("AI o'chirilgan, ovozli xabar qayta ishlanmadi.")
        return None

    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    if not api_key:
        logger.warning("Gemini API kalit yo'q, ovozli xabar qayta ishlanmadi.")
        return None

    if not client_context:
        client_context = {}

    client_name = client_context.get("full_name") or "Hali noma'lum"
    phone_status = client_context.get("phone_number") or "Hali olinmagan"
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
            history_section = f"\n--- OLDINGI SUHBAT TARIXI ---\n" + "\n".join(history_lines) + "\n"

    instruction = (
        f"{system_prompt}\n\n"
        f"--- HOZIRGI TINGLOVCHI HAQIDA ---\n"
        f"Ismi: {client_name}\n"
        f"Telefon raqami holati: {phone_status}\n"
        f"Kurs yo'nalishi: {campaign}\n"
        f"{history_section}\n"
        "--- SIZNING ASOSIY VAZIFANGIZ ---\n"
        "Tinglovchi Instagram Direct orqali sizga OVOZLI XABAR (Audio / Voice Message) yubordi.\n"
        "1. TRANSKRIPSIYA (transcription): Ovozli xabarni diqqat bilan eshiting va unda aytilgan barcha so'zlarni so'zma-so'z, aniq o'zbek yoki rus tilida matnga aylantiring (Transcribe).\n"
        "2. JAVOB (reply): Tinglovchining ovozli xabardagi savoliga xushmuomala, do'stona, qisqa (2-3 jumla), Instagram chatiga mos professional javob yozing. Agar tinglovchi telefon raqamini aytmagan bo'lsa, javobingiz oxirida unga to'liq o'quv dasturi, qabul shartlari va jadvalni yuborishimiz uchun telefon raqamini qoldirishini muloyimlik bilan so'rang.\n"
        "3. TELEFON RAQAM (extracted_phone): Agar tinglovchi ovozida o'z telefon raqamini aytgan bo'lsa, uni toza formatda (+998...) ko'rsating, aytmagan bo'lsa null.\n"
        "4. ISM (extracted_name): Agar tinglovchi o'z ismini aytgan bo'lsa ko'rsating, aks holda null.\n"
        "5. KURS YO'NALISHI (detected_course): Front Office (Mehmonxona) / Gidlik / Mehmonxona boshqaruvi / Restoran ishi / Turoperatorlik kurslaridan mosini ko'rsating.\n"
        "6. TAHLIL (summary): Tinglovchining so'rovi va ehtiyoji haqida 1 jumlalik xulosa.\n\n"
        "QAT'IY TALAB: Faqat va faqat quyidagi JSON formatida javob qaytaring:\n"
        "{\n"
        '  "transcription": "Ovozli xabar matni...",\n'
        '  "reply": "Tinglovchiga yuboriladigan javob matni...",\n'
        '  "extracted_phone": null,\n'
        '  "extracted_name": null,\n'
        '  "detected_course": "...",\n'
        '  "summary": "..."\n'
        "}"
    )

    try:
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        logger.error(f"Audio faylni base64 ga aylantirishda xatolik: {e}")
        return None

    clean_mime = mime_type.split(";")[0].strip() if ";" in mime_type else mime_type.strip()
    if not clean_mime or not clean_mime.startswith("audio/"):
        clean_mime = "audio/mp4"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": clean_mime,
                            "data": audio_b64
                        }
                    },
                    {
                        "text": instruction
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
            "maxOutputTokens": 1500
        }
    }

    headers = {"Content-Type": "application/json"}

    for model_name in [AUDIO_PRIMARY_MODEL, AUDIO_FALLBACK_MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            logger.info(f"Ovozli xabar Gemini ({model_name}) ga yuborilmoqda...")
            response = requests.post(url, json=payload, headers=headers, timeout=25)
            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        raw_json = parts[0].get("text", "").strip()
                        if raw_json.startswith("```json"):
                            raw_json = raw_json[7:]
                        elif raw_json.startswith("```"):
                            raw_json = raw_json[3:]
                        if raw_json.endswith("```"):
                            raw_json = raw_json[:-3]
                        raw_json = raw_json.strip()
                        try:
                            parsed = json.loads(raw_json)
                        except Exception:
                            parsed = json.loads(raw_json, strict=False)
                        logger.info(f"Gemini Audio ({model_name}) muvaffaqiyatli transkripsiya qildi: {parsed.get('transcription', '')[:60]}...")
                        return parsed
            else:
                logger.error(f"Gemini Audio xatosi ({model_name}) [{response.status_code}]: {response.text[:200]}")
        except Exception as e:
            logger.error(f"Gemini Audio so'rovida xatolik ({model_name}): {e}")

    return None
