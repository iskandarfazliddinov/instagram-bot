import logging
import re
from datetime import datetime
import requests
from config import settings
from database import get_client_by_id, update_client_by_id, update_client

logger = logging.getLogger(__name__)

def build_lead_message_text(client: dict, source: str = "Direct") -> str:
    full_name = client.get('full_name') or 'Noma\'lum'
    username = client.get('username') or ''
    phone = client.get('phone_number') or ''
    ig_id = client.get('instagram_id', '')
    last_msg = client.get('last_message', '')
    campaign = client.get('campaign', 'Umumiy')
    status = client.get('lead_status', 'yangi')
    manager_name = client.get('manager_name', '')
    manager_time = client.get('manager_time', '')
    is_fol = client.get('is_follower')
    ai_summary = client.get('ai_summary') or ''
    manager_comment = client.get('manager_comment') or ''

    digits = re.sub(r"\D", "", str(phone or ""))
    has_phone = len(digits) >= 9

    status_icon = "⚪"
    status_label = "Yangi (Bog'lanish kutilmoqda ⏳)"
    if status == "jarayonda":
        status_icon = "🟡"
        status_label = f"Aloqaga chiqilmoqda 📞\n👤 <b>Mas'ul:</b> {manager_name}\n🕒 <b>Qabul qildi:</b> {manager_time}"
    elif status == "boglandi":
        status_icon = "🟢"
        status_label = f"Muvaffaqiyatli bog'lanildi ✅\n👤 <b>Mas'ul:</b> {manager_name}\n🕒 <b>Vaqti:</b> {manager_time}"
    elif status == "oylanyapti":
        status_icon = "💭"
        status_label = f"Mijoz o'ylab ko'rmoqchi (Keyinroq bog'laniladi) 🤔\n👤 <b>Mas'ul:</b> {manager_name}\n🕒 <b>Vaqti:</b> {manager_time}"
    elif status == "rad":
        status_icon = "🔴"
        status_label = f"Bog'lana olmadi (Ko'tarmadi / Rad etdi) ❌\n👤 <b>Mas'ul:</b> {manager_name}\n🕒 <b>Vaqti:</b> {manager_time}"

    ig_line = f"📸 <b>Instagram:</b> <a href='https://instagram.com/{username}'>@{username}</a>\n" if username else ""
    if is_fol is not None:
        fol_str = "✅ Sahifa obunachisi ⭐" if (is_fol == 1 or is_fol is True) else "❌ Sahifaga obuna bo'lmagan"
        fol_line = f"📌 <b>Obuna holati:</b> {fol_str}\n"
    else:
        fol_line = ""

    ai_line = f"💡 <b>Mijoz ehtiyoji (AI tahlili):</b>\n<i>{ai_summary}</i>\n" if ai_summary else ""
    comment_line = f"📝 <b>Mutaxassis izohi:</b>\n<i>«{manager_comment}»</i>\n" if manager_comment else ""

    if client.get("is_reengagement"):
        if client.get("phone_updated_note") and "kiritildi" in client.get("phone_updated_note"):
            header_title = "🎉 <b>AVVAL RAQAM QOLDIRMAGAN LID TELEFON RAQAMINI YUBORDI!</b>\n"
        else:
            header_title = "🔄 <b>MIJOZDAN QAYTA MUROJAAT (YANGI SO'ROV)!</b>\n⚠️ <i>Ushbu mijoz avval ham murojaat qilgan va yana yangi kursga qiziqmoqda!</i>\n"
    elif not has_phone:
        header_title = (
            "⚠️ <b>QIZIQISH BILDIRGAN, LEKIN RAQAM QOLDIRMAGAN LID!</b>\n"
            "<i>(Mijoz savol bergan va unga eslatma (follow-up) ham yuborildi, ammo raqam qoldirmadi. "
            "Operator Direct orqali yozib ko'rishi tavsiya etiladi!)</i>\n"
        )
    else:
        header_title = "🔥 <b>INSTAGRAMDAN YANGI LID!</b>\n"

    if not has_phone:
        phone_line = "📞 <b>Telefon:</b> <i>⚠️ Raqam qoldirmadi (Faqat Direct orqali bog'lanish)</i>\n"
    else:
        phone_note = f" <i>{client.get('phone_updated_note')}</i>" if client.get("phone_updated_note") else ""
        phone_line = f"📞 <b>Telefon:</b> <code>{phone}</code>{phone_note}\n"

    text = (
        f"{header_title}"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mijoz:</b> {full_name}\n"
        f"{ig_line}"
        f"{fol_line}"
        f"{phone_line}"
        f"🎯 <b>Yo'nalish / Kurs:</b> <b>{campaign}</b>\n"
        f"📍 <b>Manba:</b> {source}\n"
        f"🆔 <b>Instagram ID:</b> <code>{ig_id}</code>\n"
        f"💬 <b>So'rovi:</b> <i>{last_msg}</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"{ai_line}"
        f"{comment_line}"
        f"{status_icon} <b>Holat:</b> {status_label}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💬 <i>Izoh qoldirish uchun ushbu xabarga 'Reply' qilib yozing (avtomatik CRM ga saqlanadi).</i>"
    )
    return text

def build_inline_keyboard(client_id: int, phone: str, status: str = "yangi", username: str = "") -> list:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9:
        clean_phone = f"998{digits}"
    else:
        clean_phone = digits

    keyboard = []
    if status == "yangi":
        keyboard.append([
            {"text": "📞 Men bog'lanaman", "callback_data": f"claim_{client_id}"},
            {"text": "✅ Bog'lanildi", "callback_data": f"done_{client_id}"}
        ])
    elif status == "jarayonda":
        keyboard.append([
            {"text": "✅ Muvaffaqiyatli gaplashildi", "callback_data": f"done_{client_id}"}
        ])
        keyboard.append([
            {"text": "🤔 Mijoz o'ylab ko'rmoqchi", "callback_data": f"thinking_{client_id}"},
            {"text": "❌ Ko'tarmadi / Rad", "callback_data": f"reject_{client_id}"}
        ])
    elif status in ["boglandi", "rad", "oylanyapti"]:
        keyboard.append([
            {"text": "🔄 Holatni o'zgartirish", "callback_data": f"claim_{client_id}"}
        ])

    quick_links = []
    if username:
        quick_links.append({"text": f"📸 @{username}", "url": f"https://instagram.com/{username}"})
    if clean_phone and len(clean_phone) >= 9:
        quick_links.append({"text": "📲 Telegram", "url": f"https://t.me/+{clean_phone}"})
    quick_links.append({"text": "💬 Izoh yozish", "callback_data": f"commentinfo_{client_id}"})
    if quick_links:
        keyboard.append(quick_links)

    return keyboard

def notify_admin_new_lead(client: dict, source: str = "Direct", allow_no_phone: bool = False):
    """
    Yangi mijoz ma'lumot qoldirganda Telegram adminiga yoki guruhiga xabar yuborish.
    MUHIM QOIDA: Telegram guruhga odatda FAQAT TELEFON RAQAMINI QOLDIRGAN haqiqiy lidlar yuboriladi!
    Agar mijozga eslatma (follow-up) yuborilib, shunda ham raqam qoldirmasa,
    operatorlar Direct orqali bog'lanishi uchun allow_no_phone=True orqali yuboriladi.
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return

    # 1. TELEFON RAQAM TEKSHIRUVI:
    phone = client.get("phone_number")
    digits = re.sub(r"\D", "", str(phone or ""))
    has_valid_phone = len(digits) >= 9

    if not has_valid_phone and not allow_no_phone:
        logger.info(f"Mijoz [{client.get('id') or client.get('instagram_id')}] hali telefon raqamini kiritmagan. Telegram guruhga yuborilmadi.")
        return

    # Client ID, tg_message_id, oldingi holat, yo'nalish va avvalgi raqamni aniqlash
    client_id = client.get("id")
    ig_id = client.get("instagram_id")
    existing_tg_mid = client.get("tg_message_id")
    prev_status = None
    prev_campaign = None
    prev_updated = None
    prev_phone = None

    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    if client_id:
        cursor.execute("SELECT tg_message_id, lead_status, campaign, updated_at, phone_number FROM clients WHERE id = ?", (client_id,))
        row = cursor.fetchone()
        if row:
            if row["tg_message_id"]:
                existing_tg_mid = row["tg_message_id"]
            prev_status = row["lead_status"]
            prev_campaign = row["campaign"]
            prev_updated = row["updated_at"]
            prev_phone = row["phone_number"]
    elif ig_id:
        cursor.execute("SELECT id, tg_message_id, lead_status, campaign, updated_at, phone_number FROM clients WHERE instagram_id = ?", (ig_id,))
        row = cursor.fetchone()
        if row:
            client_id = row["id"]
            client["id"] = client_id
            if row["tg_message_id"]:
                existing_tg_mid = row["tg_message_id"]
            prev_status = row["lead_status"]
            prev_campaign = row["campaign"]
            prev_updated = row["updated_at"]
            prev_phone = row["phone_number"]
    conn.close()

    if "prev_phone" in client:
        prev_phone = client.get("prev_phone")

    # Telefon raqami yangilanganligini tekshirish
    phone_changed = bool(prev_phone and phone and re.sub(r"\D", "", str(prev_phone)) != re.sub(r"\D", "", str(phone)))
    phone_added = bool((not prev_phone or str(prev_phone).strip() in ["", "None", "—", "null"]) and phone and len(re.sub(r"\D", "", str(phone))) >= 9)
    if phone_changed:
        client["phone_updated_note"] = f"🆕 (Yangi raqam! Avvalgi: {prev_phone})"
    elif phone_added and existing_tg_mid:
        client["phone_updated_note"] = f"🆕 (Telefon raqami kiritildi! 🎉)"

    # RE-ENGAGEMENT (Qayta murojaat, yangi raqam yoki yangi kursga qiziqish) shartlari:
    is_reengagement = False
    current_campaign = client.get("campaign", "Umumiy")
    if existing_tg_mid:
        time_diff_hours = 0
        if prev_updated:
            try:
                from datetime import datetime
                dt_prev = datetime.fromisoformat(str(prev_updated))
                time_diff_hours = (datetime.now() - dt_prev).total_seconds() / 3600
            except Exception:
                pass
        
        status_handled = (prev_status in ["boglandi", "rad", "oylanyapti"])
        campaign_changed = (prev_campaign and current_campaign and prev_campaign != current_campaign and current_campaign != "Umumiy")

        if phone_changed or phone_added or status_handled or campaign_changed or time_diff_hours >= 4:
            is_reengagement = True
            client["is_reengagement"] = True
            client["lead_status"] = "yangi"
            from database import update_client
            if ig_id:
                update_client(ig_id, lead_status="yangi")
            logger.info(f"Mijoz [{client_id}] qayta murojaat qildi (phone_changed={phone_changed}, phone_added={phone_added}, is_reengagement=True). Telegramga yangi xabar yuboriladi.")

    # Agar 1-2 soat ichidagi bir xil takroriy xabar bo'lsa -> faqat mavjud xabarni yangilaymiz (spam qilmaymiz)
    if existing_tg_mid and client_id and not is_reengagement:
        try:
            update_telegram_lead_message(client_id)
            logger.info(f"Mijoz [{client_id}] mavjud Telegram xabari yangilandi (takroriy yangi xabar yuborilmadi).")
            return
        except Exception as e:
            logger.warning(f"Telegramdagi eski xabarni yangilab bo'lmadi, yangi yuboriladi: {e}")

    client["source"] = source
    text = build_lead_message_text(client, source=source)
    keyboard = build_inline_keyboard(client_id or 0, client.get("phone_number", ""), status=client.get("lead_status", "yangi"), username=client.get("username", ""))

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": keyboard}
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            res_data = response.json()
            msg_id = res_data.get("result", {}).get("message_id")
            if msg_id:
                client["tg_message_id"] = msg_id
                if client.get("instagram_id"):
                    update_client(client["instagram_id"], tg_message_id=msg_id)
                if client.get("id"):
                    update_client_by_id(client["id"], tg_message_id=msg_id)
        else:
            logger.error(f"Telegram API javobi: {response.text}")
    except Exception as e:
        logger.error(f"Telegram bildirishnoma yuborishda xatolik: {e}")

def send_telegram_alert(text: str) -> bool:
    """
    Tizim xatolari yoki muhim ogohlantirishlarni Telegram admin/monitoring guruhiga yuborish
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload, timeout=6)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram alert yuborishda xatolik: {e}")
        return False

def handle_telegram_callback(update: dict):
    """
    Telegram guruhdagi tugmalar bosilganda mas'ul xodimni belgilash va xabarni yangilash
    """
    cq = update.get("callback_query")
    if not cq:
        return

    cq_id = cq.get("id")
    cq_data = cq.get("data", "")
    user = cq.get("from", {})
    msg = cq.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    msg_id = msg.get("message_id")
    ans_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"

    # Action va client_id ni ajratib olish
    parts = cq_data.split("_")
    if len(parts) != 2:
        try:
            requests.post(ans_url, json={"callback_query_id": cq_id, "text": "Noma'lum buyruq", "show_alert": False}, timeout=3)
        except Exception:
            pass
        return

    action, client_id_str = parts[0], parts[1]
    try:
        client_id = int(client_id_str)
    except ValueError:
        return

    if action == "commentinfo":
        try:
            requests.post(ans_url, json={
                "callback_query_id": cq_id, 
                "text": "Ushbu xabarga 'Reply' (Javob) qilib izoh yozing. U avtomatik CRM ga va xabarga saqlanadi!", 
                "show_alert": True
            }, timeout=4)
        except Exception:
            pass
        return

    # Mas'ul xodim nomini aniqlash
    username = user.get("username")
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    full_user = f"{first_name} {last_name}".strip()
    manager_label = f"@{username}" if username else full_user

    client = get_client_by_id(client_id)
    msg_text = msg.get("text", "")

    # Agar server qayta tushib client_id topilmasa, Telegram xabaridagi ma'lumotlardan avtomatik tiklash
    if not client and msg_text:
        ig_id_match = re.search(r"Instagram ID:\s*<code>?(\d+)</code>?", msg_text)
        phone_match = re.search(r"Telefon:\s*<code>?([+\d]+)</code>?", msg_text)
        name_match = re.search(r"Mijoz:\s*([^\n]+)", msg_text)
        username_match = re.search(r"@([a-zA-Z0-9_\.]+)", msg_text)
        course_match = re.search(r"Yo'nalish / Kurs:\s*<b>?([^\n<]+)</b>?", msg_text)

        ig_id = ig_id_match.group(1) if ig_id_match else None
        if ig_id:
            from database import get_or_create_client, update_client
            client = get_or_create_client(ig_id)
            updates = {}
            if phone_match:
                updates["phone_number"] = phone_match.group(1).strip()
            if name_match:
                updates["full_name"] = name_match.group(1).strip()
            if username_match:
                updates["username"] = username_match.group(1).strip()
            if course_match:
                updates["campaign"] = course_match.group(1).strip()
            if updates:
                update_client(ig_id, **updates)
                client.update(updates)
            client_id = client.get("id") or client_id

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    alert_text = "Holat yangilandi! ✅"
    new_status = client.get("lead_status", "yangi") if client else "jarayonda"

    if action == "claim":
        new_status = "jarayonda"
        alert_text = f"Siz ushbu lidga mas'ul bo'ldingiz! 📞"
    elif action == "done":
        new_status = "boglandi"
        alert_text = f"Lid yopildi: Muvaffaqiyatli bog'lanildi! ✅"
    elif action == "thinking":
        new_status = "oylanyapti"
        alert_text = f"Belgilandi: Mijoz o'ylab ko'rmoqchi 🤔"
    elif action == "reject":
        new_status = "rad"
        alert_text = f"Belgilandi: Bog'lanib bo'lmadi ❌"

    # 1. Telegram tugmasi aylanib qotib qolmasligi uchun DARHOL callback javobini berish
    try:
        requests.post(ans_url, json={"callback_query_id": cq_id, "text": alert_text, "show_alert": False}, timeout=3)
    except Exception as e:
        logger.warning(f"answerCallbackQuery xatoligi: {e}")

    if not client:
        return

    # 2. Bazada saqlash
    update_client_by_id(
        client_id,
        lead_status=new_status,
        manager_name=manager_label,
        manager_time=now_str
    )
    client["lead_status"] = new_status
    client["manager_name"] = manager_label
    client["manager_time"] = now_str

    # 3. Telegram xabarini tahrirlash (In-place update)
    new_text = build_lead_message_text(client, source=client.get("source", "Direct"))
    new_keyboard = build_inline_keyboard(client_id, client.get("phone_number", ""), status=new_status, username=client.get("username", ""))

    edit_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
    edit_payload = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": new_text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": new_keyboard}
    }
    try:
        requests.post(edit_url, json=edit_payload, timeout=5)
    except Exception as e:
        logger.error(f"Telegram editMessageText xatosi: {e}")

def handle_telegram_reply_comment(update: dict):
    """
    Xodim Telegram guruhdagi lid xabariga 'Reply' (javob) qilib izoh yozganda:
    izohni CRM ga saqlash va original Telegram xabarini yangilash
    """
    message = update.get("message")
    if not message:
        return

    reply_to = message.get("reply_to_message")
    comment_text = message.get("text", "").strip()
    if not reply_to or not comment_text:
        return

    reply_msg_id = reply_to.get("message_id")
    chat_id = message.get("chat", {}).get("id")
    from_user = message.get("from", {})
    uname = from_user.get("username")
    fname = from_user.get("first_name", "")
    lname = from_user.get("last_name", "")
    manager_name = f"@{uname}" if uname else f"{fname} {lname}".strip() or "Xodim"

    from database import get_client_by_tg_message_id, update_client_manager_comment
    client = get_client_by_tg_message_id(reply_msg_id)
    if not client:
        return

    # Izohni bazada yangilash
    updated_client = update_client_manager_comment(client["id"], comment_text, manager_name)
    if not updated_client:
        return

    # Original xabarni tahrirlab yangi izohni ko'rsatish
    new_text = build_lead_message_text(updated_client, source=updated_client.get("source", "Direct"))
    new_keyboard = build_inline_keyboard(
        updated_client["id"], 
        updated_client.get("phone_number", ""), 
        status=updated_client.get("lead_status", "yangi"), 
        username=updated_client.get("username", "")
    )
    edit_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
    requests.post(edit_url, json={
        "chat_id": chat_id,
        "message_id": reply_msg_id,
        "text": new_text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": new_keyboard}
    }, timeout=5)

    # Guruhda izoh saqlangani haqida tasdiq xabari
    ack_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(ack_url, json={
        "chat_id": chat_id,
        "reply_to_message_id": message.get("message_id"),
        "text": f"✅ <b>Izoh CRM ga saqlandi!</b>\n👤 <b>Mas'ul:</b> {manager_name}\n📝 <i>«{comment_text}»</i>",
        "parse_mode": "HTML"
    }, timeout=5)

def update_telegram_lead_message(client_id: int):
    """
    CRM dan izoh yoki holat yangilanganda Telegramdagi xabarni ham sinxronlashtirish
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return
    client = get_client_by_id(client_id)
    if not client or not client.get("tg_message_id"):
        return
    try:
        new_text = build_lead_message_text(client, source=client.get("source", "Direct"))
        new_keyboard = build_inline_keyboard(
            client_id, 
            client.get("phone_number", ""), 
            status=client.get("lead_status", "yangi"), 
            username=client.get("username", "")
        )
        edit_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
        requests.post(edit_url, json={
            "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
            "message_id": client["tg_message_id"],
            "text": new_text,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": new_keyboard}
        }, timeout=5)
    except Exception as e:
        logger.error(f"Telegram xabarni CRM dan yangilashda xato: {e}")

def notify_admin_voice_message(client: dict, transcription: str, reply: str, audio_url: str = None):
    """
    Mijoz Instagram Direct orqali ovozli xabar (Voice message) yuborganda
    Telegram guruhiga transkripsiya qilingan matni va bot javobi bilan xabar yuborish
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return

    full_name = client.get('full_name') or 'Noma\'lum'
    username = client.get('username') or ''
    phone = client.get('phone_number') or 'Hali olinmagan'
    ig_id = client.get('instagram_id', '')

    ig_line = f"📸 <b>Instagram:</b> <a href='https://instagram.com/{username}'>@{username}</a>\n" if username else ""
    phone_line = f"📞 <b>Telefon:</b> <code>{phone}</code>\n" if phone and phone != "Hali olinmagan" else ""

    text = (
        "🎙️ <b>INSTAGRAMDAN OVOZLI XABAR (VOICE) QABUL QILINDI!</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mijoz:</b> {full_name}\n"
        f"{ig_line}"
        f"{phone_line}"
        f"🆔 <b>Instagram ID:</b> <code>{ig_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🗣️ <b>Ovozli xabar matni (AI Transkripsiya):</b>\n"
        f"<i>«{transcription}»</i>\n\n"
        f"🤖 <b>AI bergan javob:</b>\n"
        f"<i>«{reply}»</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
    )

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if username:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": f"📸 Directda @{username} ga ochish", "url": f"https://instagram.com/{username}"}
            ]]
        }

    try:
        requests.post(url, json=payload, timeout=6)
    except Exception as e:
        logger.error(f"Telegram ovozli xabar bildirishnomasida xatolik: {e}")

def notify_admin_video_message(client: dict, video_title: str = "", reply: str = ""):
    """
    Mijoz Instagram Direct orqali Video/Reels yuborganda Telegram guruhiga bildirishnoma yuborish
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return

    full_name = client.get('full_name') or 'Noma\'lum'
    username = client.get('username') or ''
    phone = client.get('phone_number') or 'Hali olinmagan'
    ig_id = client.get('instagram_id', '')
    campaign = client.get('campaign', 'Umumiy')

    ig_line = f"📸 <b>Instagram:</b> <a href='https://instagram.com/{username}'>@{username}</a>\n" if username else ""
    phone_line = f"📞 <b>Telefon:</b> <code>{phone}</code>\n" if phone and phone != "Hali olinmagan" else ""
    title_line = f"🎬 <b>Video mavzusi:</b> {video_title}\n" if video_title else "🎬 <b>Video:</b> Instagram Reels / Video\n"

    text = (
        "🎬 <b>INSTAGRAMDAN VIDEO / REELS ULASHILDI!</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mijoz:</b> {full_name}\n"
        f"{ig_line}"
        f"{phone_line}"
        f"{title_line}"
        f"🎯 <b>Yo'nalish:</b> {campaign}\n"
        f"🆔 <b>Instagram ID:</b> <code>{ig_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Bot yuborgan salomlashish / javob:</b>\n"
        f"<i>«{reply}»</i>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
    )

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    if username:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": f"📸 Directda @{username} ga ochish", "url": f"https://instagram.com/{username}"}
            ]]
        }

    try:
        requests.post(url, json=payload, timeout=6)
    except Exception as e:
        logger.error(f"Telegram video bildirishnomasida xatolik: {e}")

def setup_telegram_webhook(host_url: str):
    """Render domenini Telegram Webhook sifatida ro'yxatdan o'tkazish"""
    if not settings.TELEGRAM_BOT_TOKEN:
        return False
    webhook_url = f"{host_url.rstrip('/')}/telegram-webhook"
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    try:
        resp = requests.post(url, json={"url": webhook_url}, timeout=6)
        logger.info(f"Telegram webhook o'rnatildi [{resp.status_code}]: {resp.text}")
        return resp.json().get("ok", False)
    except Exception as e:
        logger.error(f"Telegram webhook o'rnatishda xatolik: {e}")
        return False

