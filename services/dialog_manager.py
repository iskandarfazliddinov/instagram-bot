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
from services.ai_assistant import analyze_lead_need, detect_message_language, is_russian_message, is_english_message

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

    # Qiziqqan kurs yo'nalishini aniqlash (Gid qayta tayyorlash, Gid malaka oshirish, Turagentlik, Turoperatorlik va h.k.)
    history_text = (str(client.get("last_message", "")) + " " + text_clean).lower()
    detected_course = None
    detected_source = None

    if any(k in history_text for k in ["housekeeping", "xona tozalash", "frontoffice", "front office", "tourism-edu.uz", "платформ"]):
        detected_course = "Onlayn ta'lim (Front Office)"
        detected_source = "Reels: https://www.instagram.com/reel/DbM6EinhiZI/"
    elif any(k in history_text for k in ["hotel", "operations", "inavation", "innovation", "mehmonxona", "отел", "гостиниц"]):
        detected_course = "Hotel Operations and Innovation"
        detected_source = "Reels: https://www.instagram.com/reel/DeZbpoZtFw0/"
    elif any(k in history_text for k in ["malaka", "72 soat", "sertifikatim bor", "muddat tugagan", "повышение квалификации"]):
        detected_course = "Gid-ekskursiyachi (Malaka oshirish)"
    elif any(k in history_text for k in ["qayta tayyorla", "4 oy", "beyjik", "diplom", "gid", "ekskurs", "гид", "экскурсовод", "переподготовк"]):
        detected_course = "Gid-ekskursiyachi (Qayta tayyorlash)"
        detected_source = "Reels: https://www.instagram.com/reel/DbDpNKLKgll/"
    elif any(k in history_text for k in ["turagent", "турагент"]):
        detected_course = "Turagentlik kursi"
        detected_source = "Reels: https://www.instagram.com/p/DcQTeaKTBOa/"
    elif any(k in history_text for k in ["turoperator", "туроператор"]):
        detected_course = "Turoperatorlik kursi"
        detected_source = "Reels: https://www.instagram.com/p/DbXj3F1joxH/"
    elif any(k in history_text for k in ["restoran", "servis", "f&b"]):
        detected_course = "Restoran ishi va servis"
    elif any(k in history_text for k in ["narx", "qancha", "сколько стоит", "стоимость", "narxi"]):
        detected_course = "Kurslar narxi"
    elif any(k in history_text for k in ["dastur", "программ", "reja"]):
        detected_course = "O'quv dasturi"
    elif any(k in history_text for k in ["batafsil", "podrobneye", "подробнее", "malumot", "info"]):
        detected_course = "Batafsil konsultatsiya"

    upd_payload = {}
    if detected_course:
        if client.get("campaign") in ["Umumiy", "", None, "Batafsil konsultatsiya"] or (detected_course != client.get("campaign") and ("Gid" in detected_course or "kursi" in detected_course or "Hotel" in detected_course or "Front" in detected_course)):
            client["campaign"] = detected_course
            upd_payload["campaign"] = detected_course
    if detected_source and (client.get("source") in ["Direct", "", None] or not client.get("source")):
        client["source"] = detected_source
        upd_payload["source"] = detected_source

    if upd_payload:
        update_client(sender_id, **upd_payload)

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

        # AI tahlili orqali mijozning nimalarga qiziqqani va unga nima kerakligini aniqlash
        chat_history = get_client_chat_history(sender_id)
        lead_summary = analyze_lead_need(chat_history, client)
        client["ai_summary"] = lead_summary

        old_phone = client.get("phone_number")
        client["prev_phone"] = old_phone

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

        # Tilni aniqlash (mijoz qaysi tilda yozgan?)
        chat_history_now = get_client_chat_history(sender_id)
        lang_client = detect_message_language(text_clean)
        if lang_client == "uz" and chat_history_now:
            for h in chat_history_now:
                l_h = detect_message_language(h.get("text", ""))
                if l_h in ["ru", "en"]:
                    lang_client = l_h
                    break

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

        if lang_client == "en":
            final_caption = (
                f"Thank you, {client.get('full_name') or ''}! Your request has been successfully received. 😊\n\n"
                f"Our admission coordinator will contact you shortly.\n\n"
                f"You can explore our programs and international standards on our platform:"
            )
            btn_title = "Explore Platform 🌐"
        elif lang_client == "ru":
            final_caption = (
                f"Спасибо, {client.get('full_name') or ''}! Ваша заявка успешно принята. 😊\n\n"
                f"Наш специалист скоро свяжется с вами по указанному номеру и предоставит полную информацию.\n\n"
                f"По ссылке ниже вы также можете подробно ознакомиться с нашими учебными программами:"
            )
            btn_title = "Открыть платформу 🌐"
        else:
            final_caption = get_setting(
                "final_message",
                "Rahmat, tez orada siz bilan bog'lanamiz! 😊\n\nQuyidagi havola orqali akademiyamiz platformasidagi ta'lim yo'nalishlari bilan batafsil tanishishingiz mumkin:"
            )
            btn_title = "Ta'lim platformasini ochish 🚀"

        send_link_button(
            recipient_id=sender_id,
            text=final_caption,
            button_title=btn_title,
            url=send_link
        )
        append_client_chat_history(sender_id, "assistant", f"[Havola tugmasi yuborildi]: {send_link}")
        return

    # 1.5. Qayta murojaat tekshiruvi: Agar mijoz avval ro'yxatdan o'tgan bo'lsa (step == "completed")
    # va suhbat davomida yangi kurs/yo'nalish nomi tilga olinsa:
    if step == "completed":
        new_course_found = None
        for k, c_name in [
            ("malaka", "Gid malaka oshirish"),
            ("72 soat", "Gid malaka oshirish"),
            ("qayta tayyorla", "Gid qayta tayyorlash"),
            ("4 oy", "Gid qayta tayyorlash"),
            ("beyjik", "Gid qayta tayyorlash"),
            ("turagent", "Turagentlik kursi"),
            ("turoperator", "Turoperatorlik kursi"),
            ("gid", "Gid-ekskursiyachi kursi"),
            ("ekskurs", "Gid-ekskursiyachi kursi"),
            ("housekeeping", "Housekeeping (Onlayn)"),
            ("frontoffice", "Front Office (Onlayn)"),
            ("front office", "Front Office (Onlayn)"),
            ("online", "Onlayn ta'lim platformasi"),
            ("onlayn", "Onlayn ta'lim platformasi"),
            ("hotel", "Mehmonxona boshqaruvi"),
            ("mehmonxona", "Mehmonxona boshqaruvi"),
            ("restoran", "Restoran ishi va servis"),
            ("servis", "Restoran ishi va servis"),
            ("f&b", "Restoran ishi va servis")
        ]:
            if k in text_clean.lower():
                new_course_found = c_name
                break

        if new_course_found and new_course_found != client.get("campaign"):
            client["campaign"] = new_course_found
            update_client(sender_id, campaign=new_course_found, lead_status="yangi")
            if client.get("phone_number"):
                notify_admin_new_lead(client, source="Direct (Yangi kursga qiziqish 🔄)")
        elif client.get("lead_status") in ["boglandi", "rad", "oylanyapti"] and client.get("phone_number"):
            update_client(sender_id, lead_status="yangi")
            client["lead_status"] = "yangi"
            notify_admin_new_lead(client, source="Direct (Qayta murojaat 🔄)")

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
            # Agar foydalanuvchi PDF, reja yoki o'quv dasturi haqida so'ragan bo'lsa, havolalarning mavjudligini kafolatlash
            is_pdf_inquiry = any(k in text_clean.lower() for k in ["pdf", "dastur", "silabus", "syllabus", "reja", "modul", "fayl", "broshyura"])
            is_hotel_context = (
                client.get("campaign") == "Hotel Operations and Innovation" or 
                any(k in text_clean.lower() for k in ["hotel", "operations", "inavation", "innovation", "mehmonxona"]) or
                any(k in history_text for k in ["hotel", "operations", "inavation", "innovation", "mehmonxona"])
            )

            if is_pdf_inquiry or (is_hotel_context and any(k in text_clean.lower() for k in ["kurs", "dastur", "haqida", "ma'lumot", "malumot", "pdf", "reja"])):
                if "t.me/MyMarketingAndPrBot" not in ai_reply and "hotel_operations.pdf" not in ai_reply:
                    lang_msg = detect_message_language(text_clean)
                    if lang_msg == "ru":
                        links_text = (
                            "\n\n📄 Полную программу курса (PDF, 27 страниц) вы можете скачать в Telegram:\n"
                            "👉 https://t.me/MyMarketingAndPrBot?start=hotel\n\n"
                            "📥 Прямая ссылка на PDF:\n"
                            "https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n\n"
                            "📝 Форма регистрации (Zoho):\n"
                            "https://survey.zohopublic.com/zs/jQCZao"
                        )
                    elif lang_msg == "en":
                        links_text = (
                            "\n\n📄 You can download the full curriculum (PDF, 27 pages) via Telegram:\n"
                            "👉 https://t.me/MyMarketingAndPrBot?start=hotel\n\n"
                            "📥 Direct PDF download link:\n"
                            "https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n\n"
                            "📝 Application form (Zoho):\n"
                            "https://survey.zohopublic.com/zs/jQCZao"
                        )
                    else:
                        links_text = (
                            "\n\n📄 Dasturning to'liq PDF faylini (27 sahifalik o'quv rejasi) Telegram orqali yuklab olishingiz mumkin:\n"
                            "👉 https://t.me/MyMarketingAndPrBot?start=hotel\n\n"
                            "📥 Brauzerda to'g'ridan-to'g'ri yuklab olish:\n"
                            "https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n\n"
                            "📝 Ro'yxatdan o'tish (Zoho ariza):\n"
                            "https://survey.zohopublic.com/zs/jQCZao"
                        )
                    ai_reply = ai_reply.strip() + links_text

            res = send_message(sender_id, ai_reply)
            if not res or not res.get("error"):
                append_client_chat_history(sender_id, "assistant", ai_reply)
            else:
                logger.error(f"Xabar yuborilmadi (Meta rad etdi): {res}")
            if step == "start":
                update_client(sender_id, step="in_dialog")
            return
        else:
            # AI kutilmaganda javob bermay qolsa (masalan, tarmoq xatoligi bo'lsa):
            # Tinglovchi tiliga qarab ingliz, rus yoki o'zbek tilida samimiy xabar yuboriladi
            lang_req = detect_message_language(text_clean)
            if lang_req == "uz" and chat_history:
                for h in reversed(chat_history):
                    if h.get("role") == "user":
                        l_h = detect_message_language(h.get("text", ""))
                        if l_h in ["ru", "en"]:
                            lang_req = l_h
                            break

            is_pdf_inquiry = any(k in text_clean.lower() for k in ["pdf", "dastur", "silabus", "syllabus", "reja", "modul", "fayl", "broshyura"])
            is_hotel_context = (
                client.get("campaign") == "Hotel Operations and Innovation" or 
                any(k in text_clean.lower() for k in ["hotel", "operations", "inavation", "innovation", "mehmonxona"]) or
                any(k in history_text for k in ["hotel", "operations", "inavation", "innovation", "mehmonxona"])
            )

            if is_pdf_inquiry or is_hotel_context:
                if lang_req == "ru":
                    fallback_msg = (
                        "Здравствуйте! «Hotel Operations and Innovation 2026–2027» — официальная международная программа переподготовки руководителей гостиничной сферы от UN Tourism и Самаркандского кампуса Международной академии туризма.\n\n"
                        "📄 Программу курса (PDF, 27 страниц) вы можете скачать в Telegram:\n"
                        "👉 https://t.me/MyMarketingAndPrBot?start=hotel\n\n"
                        "📥 Прямая ссылка на PDF:\n"
                        "https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n\n"
                        "📝 Форма регистрации (Zoho):\n"
                        "https://survey.zohopublic.com/zs/jQCZao\n\n"
                        "Чтобы забронировать за вами место, пожалуйста, оставьте ваше имя и контактный номер телефона 😊"
                    )
                elif lang_req == "en":
                    fallback_msg = (
                        "Hello! «Hotel Operations and Innovation 2026–2027» is an official executive retraining program in collaboration with UN Tourism.\n\n"
                        "📄 Download the full curriculum (PDF, 27 pages) via Telegram:\n"
                        "👉 https://t.me/MyMarketingAndPrBot?start=hotel\n\n"
                        "📥 Direct PDF download link:\n"
                        "https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n\n"
                        "📝 Application form (Zoho):\n"
                        "https://survey.zohopublic.com/zs/jQCZao\n\n"
                        "To secure your spot, please leave your name and phone number 😊"
                    )
                else:
                    fallback_msg = (
                        "Assalomu alaykum! «Hotel Operations and Innovation 2026–2027» — UN Tourism va Xalqaro Turizm Akademiyasi Samarqand kampusining rasmiy qayta tayyorlash dasturidir.\n\n"
                        "📄 Dasturning to'liq PDF faylini (27 sahifalik o'quv rejasi) Telegram orqali yuklab olishingiz mumkin:\n"
                        "👉 https://t.me/MyMarketingAndPrBot?start=hotel\n\n"
                        "📥 Brauzerda to'g'ridan-to'g'ri yuklab olish:\n"
                        "https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n\n"
                        "📝 Ro'yxatdan o'tish (Zoho ariza):\n"
                        "https://survey.zohopublic.com/zs/jQCZao\n\n"
                        "Qabul koordinatori siz bilan bog'lanishi va joyingizni band qilish uchun, iltimos, ismingiz va telefon raqamingizni qoldiring 😊"
                    )
            elif lang_req == "en":
                fallback_msg = (
                    "Hello! Welcome to the International Tourism Academy (Samarkand Campus). 😊\n\n"
                    "To receive full details on our training programs, curriculum, and tuition fees, please leave your name and phone number:"
                )
            elif lang_req == "ru":
                fallback_msg = (
                    "Здравствуйте! Добро пожаловать в Самаркандский кампус Международной академии туризма. 😊\n\n"
                    "Чтобы мы могли отправить вам подробную учебную программу, расписание занятий и актуальную стоимость обучения, пожалуйста, оставьте ваше имя и номер телефона:"
                )
            else:
                fallback_msg = (
                    "Assalomu alaykum! Xalqaro Turizm Akademiyasi Samarqand kampusiga xush kelibsiz. 😊\n\n"
                    "Sizni qiziqtirgan barcha ta'lim yo'nalishlari va modullar bo'yicha to'liq ma'lumot, o'quv dasturi hamda narxlarni taqdim etishimiz uchun, iltimos, ismingiz va telefon raqamingizni qoldiring:"
                )

            res = send_message(sender_id, fallback_msg)
            if not res or not res.get("error"):
                append_client_chat_history(sender_id, "assistant", fallback_msg)
            else:
                logger.error(f"Fallback xabar yuborilmadi (Meta rad etdi): {res}")
            if step == "start":
                update_client(sender_id, step="awaiting_phone")
            return

    # 3. Faqat AI o'chiq bo'lsa (ai_enabled == 0) — Standart shablon bo'yicha ketadi:
    lang_user = detect_message_language(text_clean)
    if step == "awaiting_phone":
        if len(digits) < 7:
            if lang_user == "en":
                send_message(
                    sender_id,
                    "Please enter your phone number in the correct international format (e.g.: +998901234567):"
                )
            elif lang_user == "ru":
                send_message(
                    sender_id,
                    "Пожалуйста, введите ваш номер телефона в правильном формате (например: +998901234567):"
                )
            else:
                send_message(
                    sender_id, 
                    "Iltimos, telefon raqamingizni to'g'ri formatda kiriting (masalan: +998901234567):"
                )
            return

    # 3.1. Boshlang'ich holat yoki kalit so'zlarni tutish
    if any(k in text_lower for k in TRIGGER_KEYWORDS) or step == "start":
        if lang_user == "en":
            welcome_msg = (
                "Hello! Welcome to the official page of the International Tourism Academy (Samarkand Campus). 😊\n\n"
                "To receive information about our educational programs, please leave your name:"
            )
        elif lang_user == "ru":
            welcome_msg = (
                "Здравствуйте! Добро пожаловать на официальную страницу Самаркандского кампуса Международной академии туризма. 😊\n\n"
                "Чтобы получить подробную информацию об интересующих вас направлениях, пожалуйста, оставьте ваше имя:"
            )
        else:
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
        if lang_user == "en":
            response_msg = f"Thank you, {text_clean}! 🙌\n\nPlease provide your phone number so we can send you full details (e.g.: +998901234567):"
        elif lang_user == "ru":
            response_msg = f"Спасибо, {text_clean}! 🙌\n\nЧтобы мы могли отправить вам подробную информацию, пожалуйста, оставьте ваш номер телефона (например: +998901234567):"
        else:
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
        if lang_user == "en":
            send_message(
                sender_id,
                f"Your request has already been received. Official website: {default_link}\n\n"
                "Our coordinator will contact you shortly."
            )
        elif lang_user == "ru":
            send_message(
                sender_id,
                f"Ваша заявка уже принята. Наш официальный сайт: {default_link}\n\n"
                "Наш специалист скоро свяжется с вами."
            )
        else:
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

def process_incoming_video_message(sender_id: str, video_title: str = "", video_url: str = "", user_text: str = ""):
    """
    Mijoz Instagram Direct orqali Video yuborganda, Reels ulashganda yoki reklama videosi orqali yozganda:
    1. Hech qachon ovozli xabar deb qabul qilmaydi.
    2. Agar mijoz videoga qo'shib matn yozgan bo'lsa (masalan: "Расскажите подробнее" yoki "Narxi qancha?"):
       Ushbu matnni video sarlavhasi bilan birga AI orqali qayta ishlaydi va to'g'ridan-to'g'ri javob beradi.
    3. Agar mijoz shunchaki video/reels yuborgan bo'lsa (matnsiz):
       Mijoz bilan xushmuomala salomlashib, video bo'yicha qanday yordam bera olishimizni va nima ma'lumot kerakligini so'raydi.
    """
    logger.info(f"Yangi Video/Reels xabari keldi [{sender_id}]: title='{video_title}', user_text='{user_text}'")
    client = get_or_create_client(sender_id)

    # 1. Instagram profil ma'lumotlarini olish (agar mavjud bo'lmasa)
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

    # 2. Agar video sarlavhasida ma'lum bir kurs ko'rsatilgan bo'lsa, qiziqish yo'nalishini belgilash
    v_text = (video_title or "").lower()
    detected_course = None
    if "malaka" in v_text or "72 soat" in v_text:
        detected_course = "Gid malaka oshirish"
    elif "qayta tayyorla" in v_text or "4 oy" in v_text or "beyjik" in v_text:
        detected_course = "Gid qayta tayyorlash"
    elif "turagent" in v_text:
        detected_course = "Turagentlik kursi"
    elif "turoperator" in v_text:
        detected_course = "Turoperatorlik kursi"
    elif "gid" in v_text or "ekskurs" in v_text:
        detected_course = "Gid-ekskursiyachi kursi"
    elif "housekeeping" in v_text:
        detected_course = "Housekeeping (Onlayn)"
    elif "frontoffice" in v_text or "front office" in v_text:
        detected_course = "Front Office (Onlayn)"
    elif "hotel" in v_text or "mehmonxona" in v_text:
        detected_course = "Mehmonxona boshqaruvi"
    elif "restoran" in v_text or "servis" in v_text or "f&b" in v_text:
        detected_course = "Restoran ishi va servis"
    elif "online" in v_text or "onlayn" in v_text or "masofa" in v_text or "platforma" in v_text:
        detected_course = "Onlayn ta'lim platformasi"

    if detected_course:
        client["campaign"] = detected_course
        update_client(sender_id, campaign=detected_course)

    # 3. Agar mijoz videoga qo'shib matn ham yozgan bo'lsa (masalan: "Расскажите подробнее о вашей компании.")
    clean_text = (user_text or "").strip()
    if clean_text:
        if video_title and video_title.lower() not in clean_text.lower():
            combined_text = f"[{video_title}] {clean_text}"
        else:
            combined_text = clean_text
        process_incoming_message(sender_id, combined_text)
        return

    # 4. Agar foydalanuvchi shunchaki video/reels yuborgan bo'lsa (hech qanday matnsiz):
    # Salomlashib, ushbu video bo'yicha qanday yordam bera olishimizni va nima xohlashini so'raymiz
    client_name = client.get("full_name") or ""
    if client_name in ["None", "Kiritilmagan", "Noma'lum"]:
        client_name = ""
    name_str = f", {client_name}" if client_name else ""

    # Tilni aniqlash (avvalgi suhbat yoki video sarlavhasidan)
    lang = "uz"
    chat_hist = get_client_chat_history(sender_id)
    if chat_hist:
        for h in reversed(chat_hist):
            if h.get("role") == "user":
                l_h = detect_message_language(h.get("text", ""))
                if l_h in ["ru", "en"]:
                    lang = l_h
                    break
    if lang == "uz" and video_title:
        l_v = detect_message_language(video_title)
        if l_v in ["ru", "en"]:
            lang = l_v

    if lang == "ru":
        if video_title:
            reply = (
                f"Здравствуйте{name_str}! Мы получили ваше видео «{video_title}». 😊\n\n"
                f"Чем мы можем вам помочь по этому направлению? Какая информация вас интересует (стоимость, длительность обучения или программа)?"
            )
        else:
            reply = (
                f"Здравствуйте{name_str}! Мы получили ваше видео. 😊\n\n"
                f"Чем мы можем вам помочь по нашим учебным программам? Какая информация вас интересует?"
            )
    elif lang == "en":
        if video_title:
            reply = (
                f"Hello{name_str}! We have received your video regarding \"{video_title}\". 😊\n\n"
                f"How can we assist you with this program? What information would you like to know (course fees, duration, or curriculum)?"
            )
        else:
            reply = (
                f"Hello{name_str}! We have received your video. 😊\n\n"
                f"How can we assist you regarding our training programs? What information would you like to know?"
            )
    else:
        if video_title:
            reply = (
                f"Assalomu alaykum{name_str}! «{video_title}» videosi bo'yicha murojaatingizni qabul qildik. 😊\n\n"
                f"Ushbu yo'nalish bo'yicha sizga qanday yordam bera olamiz? Sizni qanday ma'lumotlar qiziqtiryapti (kurs narxi, davomiyligi yoki dars jadvali)?"
            )
        else:
            reply = (
                f"Assalomu alaykum{name_str}! Yuborgan videongizni qabul qildik. 😊\n\n"
                f"Akademiyamiz kurslari bo'yicha sizga qanday yordam bera olamiz? Sizni qaysi ta'lim yo'nalishi va ma'lumotlar qiziqtiryapti?"
            )

    send_message(sender_id, reply)

    video_label = f"🎬 [Yuborilgan video]: {video_title}" if video_title else "🎬 [Yuborilgan video / Reels]"
    update_client(sender_id, last_message=video_label, step="in_dialog")
    append_client_chat_history(sender_id, "user", video_label)
    append_client_chat_history(sender_id, "assistant", reply)

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
    audio_bytes = None
    mime_type = "audio/mp4"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        resp = requests.get(audio_url, headers=headers, timeout=25)
        if resp.status_code == 200 and resp.content:
            audio_bytes = resp.content
            raw_mime = resp.headers.get("Content-Type") or "audio/mp4"
            if ";" in raw_mime:
                raw_mime = raw_mime.split(";")[0].strip()
            mime_type = raw_mime if raw_mime.startswith("audio/") else "audio/mp4"
            logger.info(f"Audio muvaffaqiyatli yuklab olindi [{sender_id}], hajmi: {len(audio_bytes)} bayt, mime: {mime_type}")
        else:
            logger.error(f"Audio faylni yuklab bo'lmadi [{sender_id}], status: {resp.status_code}")
    except Exception as e:
        logger.error(f"Audio faylni yuklab olishda tarmoq xatoligi [{sender_id}]: {e}")

    if not audio_bytes:
        fallback_msg = "Ovozli xabaringiz qabul qilindi! 😊 Mutaxassislarimiz siz bilan tezda bog'lanishlari uchun, iltimos, ismingiz va telefon raqamingizni qoldiring:"
        send_message(sender_id, fallback_msg)
        update_client(sender_id, last_message="🎙️ [Ovozli xabar]")
        append_client_chat_history(sender_id, "user", "[Ovozli xabar]")
        append_client_chat_history(sender_id, "assistant", fallback_msg)
        return

    # 3. Gemini Multimodal Audio orqali ovozni qayta ishlash
    try:
        from services.ai_assistant import process_voice_message
        chat_history = get_client_chat_history(sender_id)
        result = process_voice_message(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            client_context=client,
            chat_history=chat_history
        )

        # Defensiv tekshirish: dict yoki tuple bo'lishi mumkin
        if isinstance(result, dict):
            transcription = (result.get("transcription") or "").strip()
            ai_reply = (result.get("reply") or "").strip()
            extracted_phone = result.get("extracted_phone")
            extracted_name = result.get("extracted_name")
            detected_course = result.get("detected_course")
            summary = result.get("summary") or ""
        elif isinstance(result, tuple):
            transcription = (result[0] or "").strip()
            ai_reply = (result[1] or "").strip()
            extracted_phone = None
            extracted_name = None
            detected_course = None
            summary = ""
        else:
            transcription = ""
            ai_reply = ""
            extracted_phone = None
            extracted_name = None
            detected_course = None
            summary = ""

        if not ai_reply:
            fallback_msg = "Ovozli xabaringizni qabul qildik! 😊 Sizni qiziqtirgan kurs bo'yicha batafsil ma'lumot va narxlarni yuborishimiz uchun telefon raqamingizni qoldiring:"
            send_message(sender_id, fallback_msg)
            update_client(sender_id, last_message="🎙️ [Ovozli xabar]")
            append_client_chat_history(sender_id, "user", "[Ovozli xabar]")
            append_client_chat_history(sender_id, "assistant", fallback_msg)
            return

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
                old_phone = client.get("phone_number")
                client["prev_phone"] = old_phone
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

        # Instagram Directga AI javobini yuborish (raqam olinmaguncha Telegram guruh bezovta qilinmaydi)
        send_message(sender_id, ai_reply)
        append_client_chat_history(sender_id, "assistant", ai_reply)

    except Exception as err:
        logger.exception(f"Ovozli xabarni qayta ishlashda kutilmagan xatolik [{sender_id}]: {err}")
        try:
            fallback_msg = "Ovozli xabaringiz qabul qilindi! 😊 Kurslarimiz bo'yicha to'liq ma'lumot va dars jadvalini yuborishimiz uchun, iltimos, telefon raqamingizni qoldiring:"
            send_message(sender_id, fallback_msg)
            append_client_chat_history(sender_id, "assistant", fallback_msg)
        except Exception:
            pass



