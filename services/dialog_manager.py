import re
import logging
from config import settings
from database import get_or_create_client, update_client
from services.instagram import send_message, send_link_button
from services.telegram import notify_admin_new_lead

logger = logging.getLogger(__name__)

# Trigger kalit so'zlar
TRIGGER_KEYWORDS = [
    "salom", "assalomu alaykum", "start", "kurs", "narx", 
    "link", "havola", "katalog", "qanaqa", "qiziq", "buyurtma"
]

def process_incoming_message(sender_id: str, user_text: str):
    """
    Direct xabarni qabul qilib, unga mos javob va havola yuborish mantiqi
    """
    client = get_or_create_client(sender_id)
    step = client.get("step", "start")
    text_clean = user_text.strip()
    text_lower = text_clean.lower()

    # Oxirgi yozilgan xabarni saqlash
    update_client(sender_id, last_message=text_clean)

    # 1. Qaytadan boshlash yoki kalit so'zlarni tutish
    if any(k in text_lower for k in TRIGGER_KEYWORDS) or step == "start":
        welcome_msg = (
            "Assalomu alaykum! Xush kelibsiz. 😊\n\n"
            "Siz so'ragan maxsus havola va batafsil ma'lumotlarni yuborishimiz uchun, "
            "iltimos, ismingizni yozib qoldiring:"
        )
        send_message(sender_id, welcome_msg)
        update_client(sender_id, step="awaiting_name")
        return

    # 2. Ism qabul qilingan bosqich -> Telefon raqam so'rash
    if step == "awaiting_name":
        # Ism sifatida qabul qilamiz
        update_client(sender_id, full_name=text_clean, step="awaiting_phone")
        response_msg = (
            f"Rahmat, {text_clean}! 🙌\n\n"
            "Havola va taklifni taqdim etishimiz uchun, iltimos, "
            "telefon raqamingizni qoldiring (masalan: +998901234567):"
        )
        send_message(sender_id, response_msg)
        return

    # 3. Telefon raqam qabul qilingan bosqich -> Bazaga yozish, Telegramga xabar va Havola berish
    if step == "awaiting_phone":
        # Oddiy telefon raqam validatsiyasi (kamida 7 ta raqam bo'lishi)
        digits = re.sub(r"\D", "", text_clean)
        if len(digits) < 7:
            send_message(
                sender_id, 
                "Iltimos, telefon raqamingizni to'g'ri formatda kiriting (masalan: +998901234567):"
            )
            return

        update_client(sender_id, phone_number=text_clean, step="completed")
        client["phone_number"] = text_clean
        client["step"] = "completed"

        # Telegram adminga xabar yuborish
        source = client.get("source", "Direct")
        notify_admin_new_lead(client, source=source)

        # Mijozga havolani yuborish
        caption = (
            "Katta rahmat! Ma'lumotlaringiz muvaffaqiyatli saqlandi. ✅\n\n"
            "Quyidagi tugma yoki havola orqali batafsil tanishishingiz mumkin:"
        )
        send_link_button(
            recipient_id=sender_id,
            text=caption,
            button_title="Havolani ochish 🚀",
            url=settings.PROMO_LINK
        )
        return

    # 4. Mijoz allaqachon ro'yxatdan o'tgan bo'lsa
    if step == "completed":
        send_message(
            sender_id,
            f"Sizning so'rovingiz qabul qilingan. Havolani yana ochish: {settings.PROMO_LINK}\n\n"
            "Agar qo'shimcha savollaringiz bo'lsa, tez orada menejerimiz sizga javob beradi."
        )
        return

def process_incoming_comment(comment_id: str, media_id: str, user_id: str, username: str, comment_text: str):
    """
    Video/Reels ostida yozilgan izohni qabul qilib, ommaviy va Direct orqali javob yuborish
    """
    logger.info(f"Yangi izoh keldi [User: {username}, Media: {media_id}]: {comment_text}")

    # Agar maxsus media IDlar berilgan bo'lsa va bu media ro'yxatda bo'lmasa, e'tiborsiz qoldiramiz
    if settings.TARGET_MEDIA_IDS and media_id not in settings.TARGET_MEDIA_IDS:
        logger.info(f"Media ID {media_id} nishondagi videolar ro'yxatida yo'q.")
        return

    # Kalit so'zlarni tekshirish (agar ro'yxat bo'sh bo'lmasa)
    text_lower = comment_text.lower()
    if settings.COMMENT_KEYWORDS:
        matched = any(k in text_lower for k in settings.COMMENT_KEYWORDS)
        if not matched:
            logger.info("Izoh kalit so'zlarga to'g'ri kelmadi.")
            return

    # 1. Izoh ostiga ommaviy javob yozish (Public reply)
    from services.instagram import reply_public_comment, send_private_reply_to_comment
    reply_public_comment(comment_id, settings.PUBLIC_COMMENT_REPLY)

    # 2. Bazada mijozni ro'yxatga olish (manbasi: Video izohi)
    client = get_or_create_client(user_id)
    update_client(
        user_id,
        source=f"Video ({media_id})",
        last_message=f"Izoh: {comment_text}",
        step="awaiting_name"
    )

    # 3. Mijozning Directiga shaxsiy xabar (Private reply) yuborish
    dm_text = (
        f"Salom! Videomiz ostida qoldirgan izohingizni ko'rdik. 😊\n\n"
        "Siz so'ragan batafsil ma'lumot va maxsus havolani yuborishimiz uchun, "
        "iltimos, ismingizni yozib qoldiring:"
    )
    send_private_reply_to_comment(comment_id, dm_text)

