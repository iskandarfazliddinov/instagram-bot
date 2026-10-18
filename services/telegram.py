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
    phone = client.get('phone_number') or 'Noma\'lum'
    ig_id = client.get('instagram_id', '')
    last_msg = client.get('last_message', '')
    campaign = client.get('campaign', 'Umumiy')
    status = client.get('lead_status', 'yangi')
    manager_name = client.get('manager_name', '')
    manager_time = client.get('manager_time', '')
    is_fol = client.get('is_follower')
    ai_summary = client.get('ai_summary') or ''
    manager_comment = client.get('manager_comment') or ''

    status_icon = "⚪"
    status_label = "Yangi (Bog'lanish kutilmoqda ⏳)"
    if status == "jarayonda":
        status_icon = "🟡"
        status_label = f"Bog'lanilmoqda ⏳\n👤 <b>Mas'ul:</b> {manager_name}\n🕒 <b>Qabul qildi:</b> {manager_time}"
    elif status == "boglandi":
        status_icon = "🟢"
        status_label = f"Muvaffaqiyatli bog'lanildi ✅\n👤 <b>Mas'ul:</b> {manager_name}\n🕒 <b>Vaqti:</b> {manager_time}"
    elif status == "oylanyapti":
        status_icon = "💭"
        status_label = f"O'ylab ko'rmoqchi (Keyinroq aloqaga chiqiladi) ⏳\n👤 <b>Mas'ul:</b> {manager_name}\n🕒 <b>Vaqti:</b> {manager_time}"
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

    text = (
        "🔥 <b>INSTAGRAMDAN YANGI LID!</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Mijoz:</b> {full_name}\n"
        f"{ig_line}"
        f"{fol_line}"
        f"📞 <b>Telefon:</b> <code>{phone}</code>\n"
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
            {"text": "⏳ O'ylayapti", "callback_data": f"thinking_{client_id}"},
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

def notify_admin_new_lead(client: dict, source: str = "Direct"):
    """
    Yangi mijoz ma'lumot qoldirganda Telegram adminiga yoki guruhiga xabar yuborish
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return

    # Client ID ni aniqlash
    client_id = client.get("id")
    if not client_id and client.get("instagram_id"):
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM clients WHERE instagram_id = ?", (client["instagram_id"],))
        row = cursor.fetchone()
        conn.close()
        if row:
            client_id = row["id"]
            client["id"] = client_id

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
        response = requests.post(url, json=payload, timeout=6)
        if response.status_code == 200:
            res_data = response.json()
            msg_id = res_data.get("result", {}).get("message_id")
            if msg_id and client.get("instagram_id"):
                update_client(client["instagram_id"], tg_message_id=msg_id)
        else:
            logger.error(f"Telegram API javobi: {response.text}")
    except Exception as e:
        logger.error(f"Telegram bildirishnoma yuborishda xatolik: {e}")

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

    # Mas'ul xodim nomini aniqlash
    username = user.get("username")
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    full_user = f"{first_name} {last_name}".strip()
    manager_label = f"@{username}" if username else full_user

    # Action va client_id ni ajratib olish
    parts = cq_data.split("_")
    if len(parts) != 2:
        return
    action, client_id_str = parts[0], parts[1]
    try:
        client_id = int(client_id_str)
    except ValueError:
        return

    if action == "commentinfo":
        ans_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        requests.post(ans_url, json={
            "callback_query_id": cq_id, 
            "text": "Ushbu xabarga 'Reply' (Javob) qilib izoh yozing. U avtomatik CRM ga va xabarga saqlanadi!", 
            "show_alert": True
        }, timeout=5)
        return

    client = get_client_by_id(client_id)
    if not client:
        return

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    alert_text = "Status yangilandi!"
    new_status = client.get("lead_status", "yangi")

    if action == "claim":
        new_status = "jarayonda"
        alert_text = f"Siz ushbu lidga mas'ul bo'ldingiz! 📞"
    elif action == "done":
        new_status = "boglandi"
        alert_text = f"Lid yopildi: Muvaffaqiyatli bog'lanildi! ✅"
    elif action == "thinking":
        new_status = "oylanyapti"
        alert_text = f"Belgilandi: Mijoz o'ylab ko'rmoqchi ⏳"
    elif action == "reject":
        new_status = "rad"
        alert_text = f"Belgilandi: Bog'lanib bo'lmadi ❌"

    # Bazada saqlash
    update_client_by_id(
        client_id,
        lead_status=new_status,
        manager_name=manager_label,
        manager_time=now_str
    )
    client["lead_status"] = new_status
    client["manager_name"] = manager_label
    client["manager_time"] = now_str

    # Telegram xabarini tahrirlash (In-place update)
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
    requests.post(edit_url, json=edit_payload, timeout=5)

    # Tugma bosilganda bildirishnoma chiqarish
    ans_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    requests.post(ans_url, json={"callback_query_id": cq_id, "text": alert_text, "show_alert": False}, timeout=5)

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

