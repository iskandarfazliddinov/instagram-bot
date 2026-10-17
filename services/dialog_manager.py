import re
import logging
from config import settings
from database import get_or_create_client, update_client, get_setting, match_campaign
from services.instagram import send_message, send_link_button
from services.telegram import notify_admin_new_lead

logger = logging.getLogger(__name__)

# Standart trigger kalit so'zlar
TRIGGER_KEYWORDS = [
    "salom", "assalomu alaykum", "start", "kurs", "narx", 
    "link", "havola", "katalog", "qanaqa", "qiziq", "buyurtma"
]

def process_incoming_message(sender_id: str, user_text: str):
    """
    Direct xabarni qabul qilib, unga mos dinamik javob va havola yuborish mantiqi
    """
    client = get_or_create_client(sender_id)
    step = client.get("step", "start")
    text_clean = user_text.strip()
    text_lower = text_clean.lower()

    # Oxirgi yozilgan xabarni saqlash
    update_client(sender_id, last_message=text_clean)

    # 1. Boshlang'ich holat yoki kalit so'zlarni tutish
    if any(k in text_lower for k in TRIGGER_KEYWORDS) or step == "start":
        # Dinamik sozlamalardan salomlashish matnini olamiz
        welcome_msg = get_setting(
            "direct_welcome",
            "Assalomu alaykum! Xush kelibsiz. 😊\n\nSiz so'ragan maxsus havola va batafsil ma'lumotlarni yuborishimiz uchun, iltimos, ismingizni yozib qoldiring:"
        )
        send_message(sender_id, welcome_msg)
        update_client(sender_id, step="awaiting_name")
        return

    # 2. Ism qabul qilingan bosqich -> Telefon raqam so'rash
    if step == "awaiting_name":
        update_client(sender_id, full_name=text_clean, step="awaiting_phone")
        ask_phone_template = get_setting(
            "ask_phone",
            "Rahmat, {name}! 🙌\n\nMa'lumotlarni taqdim etishimiz uchun telefon raqamingizni qoldiring (masalan: +998901234567):"
        )
        response_msg = ask_phone_template.replace("{name}", text_clean)
        send_message(sender_id, response_msg)
        return

    # 3. Telefon raqam qabul qilingan bosqich -> Bazaga yozish, Telegramga xabar va Havola berish
    if step == "awaiting_phone":
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

        # Telegram adminga xabar yuborish (manba va yo'nalishi bilan)
        source = client.get("source", "Direct")
        notify_admin_new_lead(client, source=source)

        # Mijoz qaysi aksiyadan kelgan bo'lsa, uning maxsus havolasi beriladi
        final_caption = get_setting(
            "final_message",
            "Katta rahmat! Ma'lumotlaringiz muvaffaqiyatli saqlandi. ✅\n\nQuyidagi havola orqali batafsil tanishishingiz mumkin:"
        )
        promo_url = client.get("last_message") # agar maxsus saqlangan bo'lsa
        default_link = get_setting("default_promo_link", settings.PROMO_LINK)

        # Havolani aniqlash (aksiya yoki standart)
        send_link = default_link
        campaign_name = client.get("campaign", "")
        if campaign_name and campaign_name != "Umumiy":
            from database import get_all_campaigns
            for c in get_all_campaigns():
                if c["name"] == campaign_name and c.get("promo_link"):
                    send_link = c["promo_link"]
                    break

        send_link_button(
            recipient_id=sender_id,
            text=final_caption,
            button_title="Havolani ochish 🚀",
            url=send_link
        )
        return

    # 4. Mijoz allaqachon ro'yxatdan o'tgan bo'lsa
    if step == "completed":
        default_link = get_setting("default_promo_link", settings.PROMO_LINK)
        send_message(
            sender_id,
            f"Sizning so'rovingiz qabul qilingan. Havolani yana ochish: {default_link}\n\n"
            "Agar qo'shimcha savollaringiz bo'lsa, tez orada menejerimiz sizga javob beradi."
        )
        return

def process_incoming_comment(comment_id: str, media_id: str, user_id: str, username: str, comment_text: str):
    """
    Video/Reels ostida yozilgan izohni qabul qilib, o'sha videoga mos maxsus javob qaytarish
    """
    logger.info(f"Yangi izoh keldi [User: {username}, Media: {media_id}]: {comment_text}")

    from services.instagram import reply_public_comment, send_private_reply_to_comment

    # 1. Ushbu video yoki kalit so'z bo'yicha maxsus qoida (aksiya) bormi, tekshiramiz
    matched = match_campaign(media_id=media_id, text=comment_text)

    if matched:
        campaign_name = matched["name"]
        public_reply_text = matched.get("public_reply") or "Directingizga batafsil ma'lumot yubordik! 📩"
        dm_welcome_text = matched.get("dm_welcome") or (
            f"Salom! {campaign_name} bo'yicha qiziqqaningiz uchun rahmat. 😊\n\n"
            "Batafsil ma'lumot va narxlarni yuborishimiz uchun ismingizni yozib qoldiring:"
        )
    else:
        # Standart umumiy qoida
        campaign_name = "Umumiy video izohi"
        public_reply_text = get_setting("public_comment_reply", settings.PUBLIC_COMMENT_REPLY)
        dm_welcome_text = (
            "Salom! Videomiz ostida qoldirgan izohingizni ko'rdik. 😊\n\n"
            "Siz so'ragan batafsil ma'lumot va maxsus havolani yuborishimiz uchun ismingizni yozib qoldiring:"
        )

    # 2. Izoh ostiga ommaviy javob yozish
    reply_public_comment(comment_id, public_reply_text)

    # 3. Bazada mijozni ro'yxatga olish (manba va qaysi aksiya ekanligi bilan)
    client = get_or_create_client(user_id)
    update_client(
        user_id,
        source=f"Video izohi ({username})",
        campaign=campaign_name,
        last_message=f"Izoh: {comment_text}",
        step="awaiting_name"
    )

    # 4. Mijozning Directiga o'sha videoga mos maxsus xabar (Private reply) yuborish
    send_private_reply_to_comment(comment_id, dm_welcome_text)


