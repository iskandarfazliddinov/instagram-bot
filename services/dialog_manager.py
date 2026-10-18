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
    Direct xabarni qabul qilib, unga mos dinamik javob, AI yordamchi va havola yuborish mantiqi
    """
    client = get_or_create_client(sender_id)
    step = client.get("step", "start")
    text_clean = user_text.strip()
    text_lower = text_clean.lower()

    # Oxirgi yozilgan xabarni saqlash
    update_client(sender_id, last_message=text_clean)

    # 1. Xabarda haqiqiy telefon raqam borligini aniqlash (kamida 9 ta raqam)
    digits = re.sub(r"\D", "", text_clean)
    has_phone = len(digits) >= 9 and ("+" in text_clean or digits.startswith("998") or len(digits) == 9)

    if has_phone:
        update_client(sender_id, phone_number=text_clean, step="completed")
        client["phone_number"] = text_clean
        client["step"] = "completed"

        # Telegram adminga xabar yuborish (manba va yo'nalishi bilan)
        source = client.get("source", "Direct")
        notify_admin_new_lead(client, source=source)

        # Mijoz qaysi aksiyadan kelgan bo'lsa, uning maxsus havolasi beriladi
        final_caption = get_setting(
            "final_message",
            "Katta rahmat! Ma'lumotlaringiz qabul qilindi. ✅\n\nQuyidagi havola orqali batafsil tanishishingiz mumkin:"
        )
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
            button_title="Rasmiy saytni ochish 🚀",
            url=send_link
        )
        return

    # 2. Sun'iy Intellekt (Gemini AI Yordamchi) orqali javob berish
    # AI yoqilgan bo'lsa, u barcha savollarga bevosita javob beradi
    ai_enabled = (get_setting("ai_enabled", "1") == "1")

    if ai_enabled:
        from services.ai_assistant import generate_ai_reply
        is_first = (step == "start")
        ai_reply = generate_ai_reply(user_message=text_clean, client_context=client, is_first_message=is_first)
        if ai_reply:
            send_message(sender_id, ai_reply)
            if step == "start":
                update_client(sender_id, step="in_dialog")
            return
        else:
            # AI kutilmaganda javob bermay qolsa (masalan, tarmoq xatoligi bo'lsa):
            # Savolni "ism" deb tushunib olmaslik uchun professional xabar qaytariladi
            fallback_msg = (
                "Xabaringiz uchun tashakkur! Xalqaro Turizm Akademiyasi Samarqand kampusi maslahatchisi tez orada sizga javob beradi. 😊\n\n"
                "Qo'shimcha ma'lumot yoki qabul bo'yicha: +998 (90) 103 30 00 yoki https://tourism-academy.uz"
            )
            send_message(sender_id, fallback_msg)
            return

    # 3. Faqat AI o'chiq bo'lsa (ai_enabled == 0) — Standart shablon bo'yicha ketadi:
    if step == "awaiting_phone":
        if len(digits) < 7:
            send_message(
                sender_id, 
                "Iltimos, telefon raqamingizni to'g'ri formatda kiriting (masalan: +998901234567):"
            )
            return

    # 3.1. Boshlang'ich holat yoki kalit so'zlarni tutish
    if any(k in text_lower for k in TRIGGER_KEYWORDS) or step == "start":
        welcome_msg = get_setting(
            "direct_welcome",
            "Assalomu alaykum! Xalqaro turizm akademiyasining Samarqand kampusi rasmiy sahifasiga xush kelibsiz. 😊\n\nSizni qiziqtirgan yo'nalishlar bo'yicha ma'lumot olish uchun, iltimos, ismingizni qoldiring:"
        )
        send_message(sender_id, welcome_msg)
        update_client(sender_id, step="awaiting_name")
        return

    # 3.2. Ism qabul qilingan bosqich -> Telefon raqam so'rash
    if step == "awaiting_name":
        update_client(sender_id, full_name=text_clean, step="awaiting_phone")
        ask_phone_template = get_setting(
            "ask_phone",
            "Rahmat, {name}! 🙌\n\nBatafsil ma'lumotlarni yuborishimiz uchun telefon raqamingizni qoldiring (masalan: +998901234567):"
        )
        response_msg = ask_phone_template.replace("{name}", text_clean)
        send_message(sender_id, response_msg)
        return

    # 3.3. Mijoz allaqachon ro'yxatdan o'tgan bo'lsa
    if step == "completed":
        default_link = get_setting("default_promo_link", settings.PROMO_LINK)
        send_message(
            sender_id,
            f"Sizning so'rovingiz qabul qilingan. Rasmiy saytimiz: {default_link}\n\n"
            "Menejerimiz tez orada siz bilan bog'lanadi."
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


