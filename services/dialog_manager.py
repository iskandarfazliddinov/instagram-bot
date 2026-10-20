import re
import logging
import requests
from config import settings
from database import (
    get_or_create_client,
    update_client,
    get_setting,
    match_campaign,
    append_client_chat_history,
    get_client_chat_history
)
from services.instagram import send_message, send_link_button, get_user_profile
from services.telegram import notify_admin_new_lead
from services.ai_assistant import analyze_lead_need

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

    # Instagram profilidan ma'lumotlarni (@username, ism, obunachi ekanligi) avtomatik olish
    if not client.get("username") or not client.get("full_name") or client.get("is_follower") is None:
        try:
            profile = get_user_profile(sender_id)
            if profile:
                prof_updates = {}
                if profile.get("username"):
                    prof_updates["username"] = profile["username"]
                    client["username"] = profile["username"]
                if profile.get("name") and (not client.get("full_name") or client.get("full_name") in ["None", "Kiritilmagan", ""]):
                    prof_updates["full_name"] = profile["name"]
                    client["full_name"] = profile["name"]
                if "is_user_follow_business" in profile:
                    is_fol = 1 if profile["is_user_follow_business"] else 0
                    prof_updates["is_follower"] = is_fol
                    client["is_follower"] = is_fol
                if prof_updates:
                    update_client(sender_id, **prof_updates)
        except Exception as e:
            logger.error(f"Instagram profil ma'lumotlarini olishda xatolik: {e}")

    # Oxirgi yozilgan xabarni saqlash va suhbat tarixiga qo'shish
    update_client(sender_id, last_message=text_clean)
    append_client_chat_history(sender_id, "user", text_clean)

    # 1. Xabarda haqiqiy telefon raqam borligini aniqlash (kamida 9 ta raqam)
    digits = re.sub(r"\D", "", text_clean)
    has_phone = len(digits) >= 9 and ("+" in text_clean or digits.startswith("998") or len(digits) == 9)

    if has_phone:
        # Telefon raqamni toza xalqaro formatga keltirish
        if len(digits) == 9:
            clean_phone = f"+998{digits}"
        elif len(digits) == 12 and digits.startswith("998"):
            clean_phone = f"+{digits}"
        else:
            clean_phone = f"+{digits}" if not text_clean.startswith("+") else text_clean

        # Agar mijoz ismini ham birga yozgan bo'lsa (masalan: "Iskandar 902857276")
        potential_name = re.sub(r"[\d\+\(\)\-\.,]", " ", text_clean).strip()
        potential_name = " ".join(potential_name.split())
        current_name = client.get("full_name")
        if (not current_name or current_name in ["None", "Noma'lum"]) and len(potential_name) >= 2:
            client["full_name"] = potential_name
            update_client(sender_id, full_name=potential_name)

        # Qiziqqan kurs yo'nalishini aniqlash
        history_text = (str(client.get("last_message", "")) + " " + text_clean).lower()
        if client.get("campaign") in ["Umumiy", "", None]:
            if "frontoffice" in history_text or "front office" in history_text:
                client["campaign"] = "Front Office (Mehmonxona)"
            elif "gid" in history_text or "ekskurs" in history_text:
                client["campaign"] = "Gid-hamrohlik / Ekskursovod"
            elif "hotel" in history_text or "mehmonxona" in history_text:
                client["campaign"] = "Mehmonxona boshqaruvi"
            elif "restoran" in history_text or "servis" in history_text or "f&b" in history_text:
                client["campaign"] = "Restoran ishi va servis"
            elif "turoperator" in history_text or "turagent" in history_text:
                client["campaign"] = "Turoperatorlik va agentlik"
            update_client(sender_id, campaign=client["campaign"])

        # AI tahlili orqali mijozning nimalarga qiziqqani va unga nima kerakligini aniqlash
        chat_history = get_client_chat_history(sender_id)
        lead_summary = analyze_lead_need(chat_history, client)
        client["ai_summary"] = lead_summary

        update_client(
            sender_id, 
            phone_number=clean_phone, 
            step="completed",
            lead_status="yangi",
            ai_summary=lead_summary
        )
        client["phone_number"] = clean_phone
        client["step"] = "completed"
        client["lead_status"] = "yangi"

        # Telegram guruhga interaktiv tugmalar bilan xabar yuborish
        source = client.get("source", "Direct")
        notify_admin_new_lead(client, source=source)

        # Mijoz qaysi aksiyadan kelgan bo'lsa, uning maxsus havolasi beriladi
        final_caption = get_setting(
            "final_message",
            "Rahmat, tez orada siz bilan bog'lanamiz! 😊\n\nQuyidagi havola orqali akademiyamiz platformasidagi ta'lim yo'nalishlari bilan batafsil tanishishingiz mumkin:"
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
            button_title="Ta'lim platformasini ochish 🚀",
            url=send_link
        )
        append_client_chat_history(sender_id, "assistant", f"[Havola tugmasi yuborildi]: {send_link}")
        return

    # 2. Sun'iy Intellekt (Gemini AI Yordamchi) orqali javob berish
    # AI yoqilgan bo'lsa, u barcha savollarga bevosita javob beradi
    ai_enabled = (get_setting("ai_enabled", "1") == "1")

    if ai_enabled:
        from services.ai_assistant import generate_ai_reply
        is_first = (step == "start")
        chat_history = get_client_chat_history(sender_id)
        ai_reply = generate_ai_reply(
            user_message=text_clean, 
            client_context=client, 
            is_first_message=is_first,
            chat_history=chat_history
        )
        if ai_reply:
            send_message(sender_id, ai_reply)
            append_client_chat_history(sender_id, "assistant", ai_reply)
            if step == "start":
                update_client(sender_id, step="in_dialog")
            return
        else:
            # AI kutilmaganda javob bermay qolsa (masalan, tarmoq xatoligi bo'lsa):
            # Quruq yoki sovuq xabar emas, samimiy va aloqa ma'lumotini oluvchi xabar yuboriladi
            fallback_msg = (
                "Assalomu alaykum! Xalqaro Turizm Akademiyasi Samarqand kampusiga xush kelibsiz. 😊\n\n"
                "Sizni qiziqtirgan barcha ta'lim yo'nalishlari va modullar bo'yicha to'liq ma'lumot, o'quv dasturi hamda narxlarni taqdim etishimiz uchun, iltimos, ismingiz va telefon raqamingizni qoldiring:"
            )
            send_message(sender_id, fallback_msg)
            append_client_chat_history(sender_id, "assistant", fallback_msg)
            if step == "start":
                update_client(sender_id, step="awaiting_phone")
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
    # 0. Cheklovlar: o'z sahifamiz yozgan javoblarni e'tiborsiz qoldiramiz va takrorlanishdan saqlaymiz
    BOT_USERNAMES = ["ita_samarkand", "ita_samarkandita_samarkand"]
    if username and username.lower() in BOT_USERNAMES:
        logger.info(f"Bot o'z izohiga javob bermaydi (ignoring self-comment: @{username})")
        return

    from database import is_comment_processed, mark_comment_processed
    if is_comment_processed(comment_id):
        logger.info(f"Izoh [{comment_id}] allaqachon qayta ishlangan. Takroriy javob yuborilmaydi.")
        return

    # Izohni darhol qayta ishlangan deb belgilaymiz (bir vaqtda kelgan so'rovlar loop yaratmasligi uchun)
    mark_comment_processed(comment_id)

    logger.info(f"Yangi haqiqiy mijoz izohi keldi [User: {username}, Media: {media_id}]: {comment_text}")

    from services.instagram import reply_public_comment, send_private_reply_to_comment

    # 1. Ushbu video ma'lumotlarini aniqlash (qaysi videoga izoh qoldirganini bilish uchun)
    from services.instagram import get_media_details
    media_info = get_media_details(media_id) if media_id else {}
    media_caption = (media_info.get("caption") or "").replace("\n", " ").strip()
    media_link = media_info.get("permalink") or ""

    # Videoning sarlavhasi / mavzusini aniqlash (birinchi 50 ta belgisi)
    short_caption = ""
    if media_caption:
        # Emosilardan tozalash va qisqa sarlavha olish
        clean_cap = media_caption[:65].strip()
        short_caption = f"«{clean_cap}...»"

    matched = match_campaign(media_id=media_id, text=comment_text)

    if matched:
        campaign_name = matched["name"]
        public_reply_text = matched.get("public_reply") or "Directingizga batafsil ma'lumot yubordik! 📩"
        dm_welcome_text = matched.get("dm_welcome") or (
            f"Salom! {campaign_name} bo'yicha qiziqqaningiz uchun rahmat. 😊\n\n"
            "Batafsil ma'lumot va narxlarni yuborishimiz uchun ismingizni yozib qoldiring:"
        )
    else:
        # Standart umumiy qoida - video nomini avtomatik chiqarish
        campaign_name = short_caption if short_caption else "Video izohi"
        public_reply_text = get_setting("public_comment_reply", settings.PUBLIC_COMMENT_REPLY)
        dm_welcome_text = (
            "Salom! Videomiz ostida qoldirgan izohingizni ko'rdik. 😊\n\n"
            "Siz so'ragan batafsil ma'lumot va maxsus havolani yuborishimiz uchun ismingizni yozib qoldiring:"
        )

    # 2. Izoh ostiga ommaviy javob yozish (faqat bir marta)
    reply_public_comment(comment_id, public_reply_text)

    # Agar AI yoqilgan bo'lsa, izohga mos aqlli va shaxsiy Direct xabar yaratamiz
    if get_setting("ai_enabled", "1") == "1":
        from services.ai_assistant import generate_ai_comment_dm
        try:
            ai_dm = generate_ai_comment_dm(
                comment_text=comment_text, 
                username=username, 
                campaign_name=media_caption[:100] if media_caption else campaign_name
            )
            if ai_dm:
                dm_welcome_text = ai_dm
        except Exception as e:
            logger.error(f"AI Comment DM yaratishda xato: {e}")

    # 3. Bazada mijozni ro'yxatga olish (qaysi video ekanligi, havolasi va sarlavhasi bilan)
    client = get_or_create_client(user_id)
    
    # Aniq manba matni
    if media_link:
        source_label = f"Reels: {media_link}"
    elif short_caption:
        source_label = f"Video: {short_caption}"
    else:
        source_label = f"Video izohi (@{username})" if username else "Video izohi"

    last_msg_label = f"Izoh: «{comment_text}» ({short_caption})" if short_caption else f"Izoh: «{comment_text}»"

    c_updates = {
        "source": source_label,
        "campaign": campaign_name,
        "last_message": last_msg_label,
        "step": "awaiting_name"
    }

    if username:
        c_updates["username"] = username

    try:
        profile = get_user_profile(user_id)
        if profile:
            if profile.get("username") and not username:
                c_updates["username"] = profile["username"]
            if profile.get("name") and (not client.get("full_name") or client.get("full_name") in ["None", "Kiritilmagan", ""]):
                c_updates["full_name"] = profile["name"]
            if "is_user_follow_business" in profile:
                c_updates["is_follower"] = 1 if profile["is_user_follow_business"] else 0
    except Exception as e:
        logger.error(f"Izoh qoldirgan foydalanuvchi profilini olishda xato: {e}")

    update_client(user_id, **c_updates)

    # 4. Mijozning Directiga o'sha videoga mos maxsus xabar (Private reply) yuborish
    send_private_reply_to_comment(comment_id, dm_welcome_text)
    append_client_chat_history(user_id, "user", f"[Video izohi]: {comment_text}")
    append_client_chat_history(user_id, "assistant", dm_welcome_text)

def process_incoming_audio_message(sender_id: str, audio_url: str):
    """
    Mijoz Instagram Direct orqali Ovozli xabar (Voice message) yuborganda:
    1. Ovozli faylni yuklab oladi.
    2. Gemini Multimodal Audio orqali ovozni tinglab matnga (Transcribe) aylantiradi va professional javob tayyorlaydi.
    3. Agar ovozda telefon raqam aytilgan bo'lsa, uni bazaga saqlab Telegramga yangi lid sifatida uzatadi.
    4. Instagram Directga AI tayyorlagan javobni yuboradi.
    5. CRM bazasiga suhbat tarixi va ovozli xabar matnini yozadi.
    """
    logger.info(f"Ovozli xabar qabul qilindi [{sender_id}], yuklab olinmoqda...")
    client = get_or_create_client(sender_id)

    # 1. Instagram profilini tekshirish
    if not client.get("username") or not client.get("full_name") or client.get("is_follower") is None:
        try:
            profile = get_user_profile(sender_id)
            if profile:
                prof_updates = {}
                if profile.get("username"):
                    prof_updates["username"] = profile["username"]
                    client["username"] = profile["username"]
                if profile.get("name") and (not client.get("full_name") or client.get("full_name") in ["None", "Kiritilmagan", ""]):
                    prof_updates["full_name"] = profile["name"]
                    client["full_name"] = profile["name"]
                if "is_user_follow_business" in profile:
                    is_fol = 1 if profile["is_user_follow_business"] else 0
                    prof_updates["is_follower"] = is_fol
                    client["is_follower"] = is_fol
                if prof_updates:
                    update_client(sender_id, **prof_updates)
        except Exception as e:
            logger.error(f"Instagram profil ma'lumotlarini olishda xatolik: {e}")

    # 2. Audio faylni yuklab olish
    try:
        resp = requests.get(audio_url, timeout=20)
        if resp.status_code != 200:
            logger.error(f"Audio faylni yuklab bo'lmadi [status {resp.status_code}]")
            send_message(sender_id, "Ovozli xabaringiz qabul qilindi! Mutaxassislarimiz siz bilan bog'lanishlari uchun, iltimos, telefon raqamingizni qoldiring 😊")
            return
        audio_bytes = resp.content
        mime_type = resp.headers.get("Content-Type") or "audio/mp4"
        if ";" in mime_type:
            mime_type = mime_type.split(";")[0].strip()
        if not mime_type.startswith("audio/"):
            mime_type = "audio/mp4"
    except Exception as e:
        logger.error(f"Audio faylni yuklab olishda tarmoq xatoligi: {e}")
        send_message(sender_id, "Ovozli xabaringiz uchun rahmat! Sizga to'liq ma'lumot yuborishimiz uchun, iltimos, ismingiz va telefon raqamingizni yozib qoldiring 😊")
        return

    # 3. Gemini Multimodal Audio orqali ovozni qayta ishlash
    from services.ai_assistant import process_voice_message
    chat_history = get_client_chat_history(sender_id)
    result = process_voice_message(
        audio_bytes=audio_bytes,
        mime_type=mime_type,
        client_context=client,
        chat_history=chat_history
    )

    if not result:
        fallback_msg = "Ovozli xabaringizni qabul qildik! 😊 Sizni qiziqtirgan kurs bo'yicha batafsil ma'lumot va narxlarni yuborishimiz uchun telefon raqamingizni qoldiring:"
        send_message(sender_id, fallback_msg)
        update_client(sender_id, last_message="🎙️ [Ovozli xabar]")
        append_client_chat_history(sender_id, "user", "[Ovozli xabar]")
        append_client_chat_history(sender_id, "assistant", fallback_msg)
        return

    transcription = result.get("transcription", "").strip()
    ai_reply = result.get("reply", "").strip()
    extracted_phone = result.get("extracted_phone")
    extracted_name = result.get("extracted_name")
    detected_course = result.get("detected_course")
    summary = result.get("summary", "")

    logger.info(f"Ovozli xabar transkripsiyasi [{sender_id}]: «{transcription}»")

    display_msg = f"🎙️ {transcription}" if transcription else "🎙️ [Ovozli xabar]"
    updates = {"last_message": display_msg}
    if summary:
        updates["ai_summary"] = summary
        client["ai_summary"] = summary

    if extracted_name and (not client.get("full_name") or client.get("full_name") in ["None", "Kiritilmagan", ""]):
        updates["full_name"] = extracted_name
        client["full_name"] = extracted_name

    if detected_course and detected_course not in ["Umumiy", "", None] and client.get("campaign") in ["Umumiy", "", None]:
        updates["campaign"] = detected_course
        client["campaign"] = detected_course

    append_client_chat_history(sender_id, "user", f"[Ovozli xabar]: {transcription}" if transcription else "[Ovozli xabar]")

    # 4. Agar ovozda telefon raqami aytilgan bo'lsa -> To'liq Lid yaratiladi
    if extracted_phone:
        digits = re.sub(r"\D", "", str(extracted_phone))
        if len(digits) >= 9:
            clean_phone = f"+998{digits[-9:]}" if len(digits) == 9 or (len(digits) == 12 and digits.startswith("998")) else f"+{digits}"
            updates["phone_number"] = clean_phone
            updates["step"] = "completed"
            updates["lead_status"] = "yangi"
            client["phone_number"] = clean_phone
            client["step"] = "completed"
            client["lead_status"] = "yangi"

            update_client(sender_id, **updates)

            # Telegram guruhiga to'liq lid xabarini yuborish
            notify_admin_new_lead(client, source="Direct (Ovozli xabar 🎙️)")

            # Mijozga javob va platforma havolasini yuborish
            if ai_reply:
                send_message(sender_id, ai_reply)
                append_client_chat_history(sender_id, "assistant", ai_reply)

            final_caption = get_setting(
                "final_message",
                "Rahmat, tez orada siz bilan bog'lanamiz! 😊\n\nQuyidagi havola orqali akademiyamiz platformasidagi ta'lim yo'nalishlari bilan tanishishingiz mumkin:"
            )
            default_link = get_setting("default_promo_link", settings.PROMO_LINK)
            send_link_button(
                recipient_id=sender_id,
                text=final_caption,
                button_title="Ta'lim platformasini ochish 🚀",
                url=default_link
            )
            append_client_chat_history(sender_id, "assistant", f"[Havola tugmasi yuborildi]: {default_link}")
            return

    # 5. Agar telefon raqam hali aytilmagan bo'lsa
    update_client(sender_id, **updates)

    # Telegram guruhga ovozli xabar kelgani haqida xabarnoma yuborish
    from services.telegram import notify_admin_voice_message
    notify_admin_voice_message(client, transcription=transcription or "Ovoz eshitilmadi", reply=ai_reply or "—")

    # Instagram Directga AI javobini yuborish
    if ai_reply:
        send_message(sender_id, ai_reply)
        append_client_chat_history(sender_id, "assistant", ai_reply)



