import logging
import requests
from config import settings
from database import get_setting

logger = logging.getLogger(__name__)

PRIMARY_MODEL = "gemini-flash-lite-latest"
FALLBACK_MODEL = "gemini-3.5-flash-lite"

def generate_ai_reply(user_message: str, client_context: dict, is_first_message: bool = False) -> str | None:
    """
    Google Gemini AI orqali mijoz xabariga professional va samimiy javob yaratish
    """
    # 1. AI yoqilganligini tekshirish
    if get_setting("ai_enabled", "1") != "1":
        return None

    # 2. API kalitni olish (baza yoki .env dan)
    api_key = get_setting("gemini_api_key", "").strip() or settings.GEMINI_API_KEY.strip()
    if not api_key:
        logger.info("AI Yordamchi yoqilgan, lekin Gemini API kalit kiritilmagan.")
        return None

    # 3. Tizim yo'riqnomasi (System prompt / Bilimlar bazasi)
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

    context_prompt = (
        f"{system_prompt}\n\n"
        f"--- HOZIRGI TINGLOVCHI/MIJOZ HAQIDA MA'LUMOT ---\n"
        f"Mijoz ismi: {client_name}\n"
        f"Telefon raqami holati: {phone_status}\n"
        f"Qiziqqan yo'nalishi/aksiyasi: {campaign}\n"
        f"{greeting_instruction}\n"
        f"Eslatma: Agar mijoz hali telefon raqamini bermagan bo'lsa, javobingiz oxirida "
        f"unga batafsil ma'lumot va dars jadvalini yuborish uchun muloyimlik bilan telefon raqamini so'rang. "
        f"Javobingiz Instagram chatiga mos, qisqa (2-3 jumla), o'ta xushmuomala va samimiy bo'lsin."
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
            "temperature": 0.5,
            "maxOutputTokens": 800
        }
    }

    headers = {"Content-Type": "application/json"}

    # Birlamchi va zaxira modellar orqali so'rov yuborish
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=12)
            data = response.json()

            if response.status_code == 200:
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        ai_text = parts[0].get("text", "").strip()
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

    # Muloqot matnini yig'ish
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

    # Agar API kalit bo'lsa, Gemini AI orqali aniq tahlil olamiz
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
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 300}
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
                            summary = parts[0].get("text", "").strip()
                            if summary:
                                logger.info(f"AI Lead tahlili ({model_name}): {summary}")
                                return summary
            except Exception as e:
                logger.error(f"AI Lead tahlilida xatolik ({model_name}): {e}")

    # Fallback evristik tahlil (agar AI ishlamasa yoki so'rov qisqa bo'lsa)
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

