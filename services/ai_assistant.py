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
