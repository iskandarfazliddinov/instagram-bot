import logging
import requests
from config import settings

logger = logging.getLogger(__name__)

def notify_admin_new_lead(client: dict, source: str = "Direct"):
    """
    Yangi mijoz ma'lumot qoldirganda Telegram adminiga yoki guruhiga xabar yuborish
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return

    full_name = client.get('full_name', 'Noma\'lum')
    phone = client.get('phone_number', 'Noma\'lum')
    ig_id = client.get('instagram_id', '')
    last_msg = client.get('last_message', '')

    text = (
        "🔥 <b>INSTAGRAMDAN YANGI LID!</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mijoz:</b> {full_name}\n"
        f"📞 <b>Telefon:</b> <code>{phone}</code>\n"
        f"📍 <b>Manba:</b> {source}\n"
        f"🆔 <b>Instagram ID:</b> <code>{ig_id}</code>\n"
        f"💬 <b>So'rovi:</b> <i>{last_msg}</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "✅ <i>Mijozga maxsus havola yuborildi. Tezda bog'lanish tavsiya etiladi!</i>"
    )

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            logger.error(f"Telegram API javobi: {response.text}")
    except Exception as e:
        logger.error(f"Telegram bildirishnoma yuborishda xatolik: {e}")

