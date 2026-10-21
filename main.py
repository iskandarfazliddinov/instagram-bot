import asyncio
import io
import csv
import logging
import hashlib
import urllib.parse
from fastapi import FastAPI, Request, Response, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from config import settings
from database import (
    init_db,
    get_all_clients,
    get_all_settings,
    set_setting,
    get_setting,
    get_all_campaigns,
    create_campaign,
    delete_campaign,
    delete_client_by_id,
    clear_all_clients,
    update_client_by_id,
    update_client_manager_comment
)
from services.dialog_manager import (
    process_incoming_message,
    process_incoming_comment,
    process_incoming_audio_message
)
from services.instagram import get_recent_media, resolve_media_id_from_url
from services.admin_view import get_admin_dashboard_html, get_login_page_html
from services.telegram import (
    handle_telegram_callback,
    handle_telegram_reply_comment,
    update_telegram_lead_message,
    setup_telegram_webhook
)

# Loglarni sozlash
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def follow_up_background_worker():
    """
    Suhbati yakunlanmagan (telefon raqamini qoldirmagan) mijozlarga
    AI orqali avtomatik aqlli eslatma (Follow-up) yuboruvchi xizmat
    """
    await asyncio.sleep(60)  # Server ishga tushgandan so'ng 1 daqiqa kutish
    while True:
        try:
            if get_setting("ai_followup_enabled", "1") == "1":
                try:
                    delay_mins = int(get_setting("ai_followup_delay_minutes", "30"))
                except ValueError:
                    delay_mins = 30

                from database import (
                    get_abandoned_clients,
                    mark_client_followup_sent,
                    get_client_chat_history,
                    append_client_chat_history
                )
                from services.ai_assistant import generate_ai_followup
                from services.instagram import send_message

                abandoned_clients = get_abandoned_clients(min_minutes=delay_mins, max_hours=23)
                for client in abandoned_clients:
                    ig_id = client.get("instagram_id")
                    if not ig_id:
                        continue

                    history = get_client_chat_history(ig_id)
                    followup_msg = generate_ai_followup(history, client)
                    if followup_msg:
                        logger.info(f"AI Follow-up yuborilmoqda [{ig_id}]: {followup_msg[:45]}...")
                        send_message(ig_id, followup_msg)
                        append_client_chat_history(ig_id, "assistant", followup_msg)
                        mark_client_followup_sent(client["id"])
                        await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Follow-up fon xizmati xatoligi: {e}")

        # Har 5 daqiqada tekshirish
        await asyncio.sleep(300)

async def token_auto_refresh_worker():
    """
    Instagram 60 kunlik tokenini muddati tugamasdan avtomatik yangilash (Auto-Refresh)
    """
    await asyncio.sleep(120)  # Server ishga tushgandan so'ng 2 daqiqa kutish
    while True:
        try:
            from services.instagram import refresh_long_lived_token
            refresh_long_lived_token()
        except Exception as e:
            logger.error(f"Token auto-refresh xatoligi: {e}")
        # Har 24 soatda tekshirish
        await asyncio.sleep(86400)

app = FastAPI(
    title="Instagram Automation & Lead Capture API",
    description="Instagram Direct va Video izohlari orqali avtomatik javob berish, havola ulashish va Telegramga lidlarni uzatish tizimi",
    version="1.1.0"
)

@app.on_event("startup")
async def on_startup():
    init_db()
    try:
        setup_telegram_webhook("https://instagram-bot-zohg.onrender.com")
    except Exception as e:
        logger.error(f"Telegram webhook ulashda xatolik: {e}")
    asyncio.create_task(follow_up_background_worker())
    asyncio.create_task(token_auto_refresh_worker())
    logger.info("Ma'lumotlar bazasi, AI Follow-up va Token Auto-Refresh xizmati ishga tushirildi.")

@app.get("/")
def home():
    return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/privacy", response_class=Response)
def privacy_policy():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Privacy Policy - LeadAuto</title></head>
    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: auto;">
        <h1>Privacy Policy</h1>
        <p>Last updated: October 2026</p>
        <p>LeadAuto respects your privacy and is committed to protecting user personal data. We only process information (such as name and phone number) that you voluntarily provide to us via Instagram Direct for the purpose of customer service and business communication.</p>
        <h3>Data Protection</h3>
        <p>We do not sell, rent, or share your personal contact details with third-party advertising companies.</p>
        <h3>Contact & Data Deletion</h3>
        <p>If you wish to have your data removed from our database, please contact us at iskandarfazliddinov48@gmail.com.</p>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")

@app.get("/terms", response_class=Response)
def terms_of_service():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Terms of Service - LeadAuto</title></head>
    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: auto;">
        <h1>Terms of Service</h1>
        <p>By interacting with our Instagram automated customer assistant, you agree to receive automated messages regarding your inquiries, product catalogs, and service details.</p>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")

@app.get("/data-deletion", response_class=Response)
def data_deletion():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>User Data Deletion Instructions</title></head>
    <body style="font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: auto;">
        <h1>User Data Deletion Instructions</h1>
        <p>To request deletion of your information stored during customer inquiries, please email iskandarfazliddinov48@gmail.com with your Instagram username or phone number. Your data will be deleted within 24 hours.</p>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")

# ----------------- META WEBHOOK ROUTELARI -----------------

@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Meta (Facebook Developers) serverni tekshirish uchun yuboradigan GET so'rovi (Handshake)
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.VERIFY_TOKEN:
        logger.info("Meta Webhook muvaffaqiyatli tasdiqlandi!")
        return Response(content=challenge, media_type="text/plain")

    logger.warning("Noto'g'ri verify_token bilan so'rov keldi!")
    return Response(status_code=status.HTTP_403_FORBIDDEN)

@app.post("/webhook")
async def receive_instagram_events(request: Request):
    """
    Instagram Direct va Videolardagi izohlarni qabul qilish
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid json"}

    if body.get("object") == "instagram" or "field" in body:
        # Agar Meta test oynasidan to'g'ridan-to'g'ri test xabar yuborilgan bo'lsa
        if body.get("field") == "messages":
            val = body.get("value", {})
            sender_id = val.get("sender", {}).get("id")
            msg_text = val.get("message", {}).get("text", "")
            if sender_id and msg_text:
                logger.info(f"Test xabar keldi [{sender_id}]: {msg_text}")
                process_incoming_message(sender_id, msg_text)
            return {"status": "ok"}

        for entry in body.get("entry", []):
            # 1. Standart Messenger API formati (entry -> messaging)
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message = messaging_event.get("message", {})

                # Bot o'zi yuborgan xabarning aks sadosi (echo) bo'lsa e'tiborsiz qoldiramiz
                if message.get("is_echo"):
                    continue

                if "text" in message:
                    user_text = message.get("text", "")
                    logger.info(f"Yangi Direct xabar keldi [{sender_id}]: {user_text}")
                    process_incoming_message(sender_id, user_text)
                elif "attachments" in message:
                    for att in message.get("attachments", []):
                        att_type = att.get("type")
                        att_url = att.get("payload", {}).get("url")
                        if att_type in ["audio", "voice"] or (att_url and any(ext in att_url.lower() for ext in [".mp4", ".m4a", ".mp3", ".ogg", ".aac", ".wav"])):
                            logger.info(f"Yangi Direct ovozli xabar keldi [{sender_id}]")
                            process_incoming_audio_message(sender_id, att_url)
                elif "quick_reply" in message:
                    payload = message["quick_reply"].get("payload", "")
                    process_incoming_message(sender_id, payload)

            # 2. Yangi Instagram API formati (entry -> changes)
            for change in entry.get("changes", []):
                field = change.get("field")
                value = change.get("value", {})

                # A) Direct xabarlar (Instagram API v26.0)
                if field == "messages":
                    sender_id = value.get("sender", {}).get("id")
                    message = value.get("message", {})

                    if message.get("is_echo"):
                        continue

                    if "text" in message:
                        user_text = message.get("text", "")
                        logger.info(f"Yangi Direct xabar (v26.0) keldi [{sender_id}]: {user_text}")
                        process_incoming_message(sender_id, user_text)
                    elif "attachments" in message:
                        for att in message.get("attachments", []):
                            att_type = att.get("type")
                            att_url = att.get("payload", {}).get("url")
                            if att_type in ["audio", "voice"] or (att_url and any(ext in att_url.lower() for ext in [".mp4", ".m4a", ".mp3", ".ogg", ".aac", ".wav"])):
                                logger.info(f"Yangi Direct ovozli xabar (v26.0) keldi [{sender_id}]")
                                process_incoming_audio_message(sender_id, att_url)

                # B) Video/Reels izohlari
                elif field == "comments":
                    comment_id = value.get("id")
                    comment_text = value.get("text", "")
                    media_id = value.get("media", {}).get("id", "")
                    from_user = value.get("from", {})
                    user_id = from_user.get("id")
                    username = from_user.get("username", "")

                    if comment_id and user_id:
                        process_incoming_comment(
                            comment_id=comment_id,
                            media_id=media_id,
                            user_id=user_id,
                            username=username,
                            comment_text=comment_text
                        )

    return {"status": "ok"}

# ----------------- CRM AVTORIZATSIYA VA XAVFSIZLIK -----------------

def get_auth_token() -> str:
    pwd = get_setting("admin_password", "admin")
    return hashlib.sha256(f"{pwd}_crm_salt_2026".encode()).hexdigest()

def is_authenticated(request: Request) -> bool:
    token = request.cookies.get("crm_session")
    return bool(token and token == get_auth_token())

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    """CRM tizimiga kirish sahifasi"""
    if is_authenticated(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    return HTMLResponse(content=get_login_page_html(error=error))

@app.post("/login")
def login_action(
    username: str = Form(...),
    password: str = Form(...)
):
    """Login va parolni tekshirib sessiya o'rnatish"""
    expected_user = get_setting("admin_username", "admin").strip()
    expected_pwd = get_setting("admin_password", "admin").strip()

    if username.strip() == expected_user and password.strip() == expected_pwd:
        resp = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie(
            key="crm_session",
            value=get_auth_token(),
            httponly=True,
            max_age=86400 * 30, # 30 kun saqlanadi
            samesite="lax"
        )
        return resp
    else:
        return RedirectResponse(
            url="/login?error=Login+yoki+parol+noto%27g%27ri",
            status_code=status.HTTP_303_SEE_OTHER
        )

@app.get("/logout")
def logout():
    """Tizimdan chiqish (sessiyani tozalash)"""
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("crm_session")
    return resp

# ----------------- ADMIN VA CRM BOSHQARUVI -----------------

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, notice: str = ""):
    """Instagram CRM boshqaruv paneli"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    settings_data = get_all_settings()
    campaigns_data = get_all_campaigns()
    clients_data = get_all_clients()
    recent_media = get_recent_media(limit=25)
    html_content = get_admin_dashboard_html(
        settings_data, campaigns_data, clients_data,
        recent_media=recent_media, notice=notice
    )
    return HTMLResponse(content=html_content)

@app.post("/admin/settings/save")
async def save_settings(
    request: Request,
    page_access_token: str = Form(""),
    direct_welcome: str = Form(""),
    ask_phone: str = Form(""),
    final_message: str = Form(""),
    default_promo_link: str = Form("")
):
    """Direct xabar shablonlari va Instagram tokenni yangilash"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if page_access_token.strip():
        set_setting("page_access_token", page_access_token.strip())
    if direct_welcome.strip():
        set_setting("direct_welcome", direct_welcome.strip())
    if ask_phone.strip():
        set_setting("ask_phone", ask_phone.strip())
    if final_message.strip():
        set_setting("final_message", final_message.strip())
    if default_promo_link.strip():
        set_setting("default_promo_link", default_promo_link.strip())

    return RedirectResponse(
        url="/admin?notice=Sozlamalar+va+Instagram+token+muvaffaqiyatli+saqlandi#templates",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.get("/api/check-token")
def check_token_api(request: Request, token: str = ""):
    """Instagram Page Access Token holatini tekshirish API"""
    if not is_authenticated(request):
        return {"ok": False, "error": "Ruxsat berilmagan (Avtorizatsiyadan o'ting)"}
    from services.instagram import check_instagram_token
    return check_instagram_token(token=token if token.strip() else None)

@app.post("/admin/campaign/create")
async def add_campaign(
    request: Request,
    name: str = Form(...),
    video_url: str = Form(""),
    trigger_keyword: str = Form(""),
    public_reply: str = Form(...),
    promo_link: str = Form(...),
    dm_welcome: str = Form("")
):
    """Yangi video qoidasi qo'shish"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    media_id, resolved_url = resolve_media_id_from_url(video_url)
    create_campaign(
        name=name,
        trigger_keyword=trigger_keyword,
        media_id=media_id,
        media_url=resolved_url or video_url,
        public_reply=public_reply,
        dm_welcome=dm_welcome,
        promo_link=promo_link
    )
    msg = "Yangi video qoidasi muvaffaqiyatli saqlandi!"
    return RedirectResponse(
        url=f"/admin?notice={urllib.parse.quote(msg)}#campaigns",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/campaign/delete")
async def remove_campaign(request: Request, campaign_id: int = Form(...)):
    """Video qoidasini o'chirish"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    delete_campaign(campaign_id)
    return RedirectResponse(
        url="/admin?notice=Video+qoidasi+o%27chirildi#campaigns",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/ai/save")
async def save_ai_settings(
    request: Request,
    ai_enabled: str = Form(None),
    ai_followup_enabled: str = Form(None),
    ai_followup_delay_minutes: str = Form("30"),
    gemini_api_key: str = Form(""),
    ai_system_prompt: str = Form("")
):
    """Sun'iy intellekt (Gemini AI) sozlamalarini saqlash"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    is_on = "1" if ai_enabled else "0"
    set_setting("ai_enabled", is_on)

    is_followup_on = "1" if ai_followup_enabled else "0"
    set_setting("ai_followup_enabled", is_followup_on)
    if ai_followup_delay_minutes.strip():
        set_setting("ai_followup_delay_minutes", ai_followup_delay_minutes.strip())

    if gemini_api_key.strip():
        set_setting("gemini_api_key", gemini_api_key.strip())
    if ai_system_prompt.strip():
        set_setting("ai_system_prompt", ai_system_prompt.strip())

    msg = "Sun'iy Intellekt sozlamalari muvaffaqiyatli saqlandi!"
    return RedirectResponse(
        url=f"/admin?notice={urllib.parse.quote(msg)}#ai",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/security/save")
def save_security_settings(
    request: Request,
    username: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    """CRM login va parolini yangilash"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if new_password.strip() != confirm_password.strip():
        return RedirectResponse(
            url="/admin?notice=Xatolik:+Yangi+parollar+mos+tushmadi#security",
            status_code=status.HTTP_303_SEE_OTHER
        )

    if len(new_password.strip()) < 3:
        return RedirectResponse(
            url="/admin?notice=Xatolik:+Parol+juda+qisqa#security",
            status_code=status.HTTP_303_SEE_OTHER
        )

    set_setting("admin_username", username.strip())
    set_setting("admin_password", new_password.strip())

    resp = RedirectResponse(
        url="/admin?notice=Login+va+parol+muvaffaqiyatli+yangilandi#security",
        status_code=status.HTTP_303_SEE_OTHER
    )
    resp.set_cookie(
        key="crm_session",
        value=get_auth_token(),
        httponly=True,
        max_age=86400 * 30,
        samesite="lax"
    )
    return resp

@app.post("/admin/clients/clear")
def clear_clients(request: Request):
    """Barcha test ma'lumotlarini tozalash"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    clear_all_clients()
    return RedirectResponse(
        url="/admin?notice=Barcha+test+lidlar+muvaffaqiyatli+tozalandi!#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/clients/{client_id}/delete")
def delete_single_client(client_id: int, request: Request):
    """Bitta lidni o'chirish"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    delete_client_by_id(client_id)
    return RedirectResponse(
        url="/admin?notice=Lid+muvaffaqiyatli+o%27chirildi#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.post("/admin/clients/{client_id}/status")
def update_status_from_admin(
    client_id: int,
    request: Request,
    status_val: str = Form(..., alias="status"),
    manager_name: str = Form("Admin", alias="manager_name")
):
    """Admin paneldan mijoz holati va mas'ul xodimni to'g'ridan-to'g'ri o'zgartirish"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    from datetime import datetime
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    update_client_by_id(client_id, lead_status=status_val, manager_name=manager_name, manager_time=now_str)
    
    try:
        update_telegram_lead_message(client_id)
    except Exception as e:
        logger.error(f"Telegram lead update error from CRM: {e}")

    return RedirectResponse(
        url="/admin?notice=Mijoz+holati+muvaffaqiyatli+yangilandi#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/clients/{client_id}/comment")
def update_comment_from_admin(
    client_id: int,
    request: Request,
    comment: str = Form(...)
):
    """CRM dan mutaxassis izohini saqlash va Telegram guruhidagi xabarni yangilash"""
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    update_client_manager_comment(client_id, comment, manager_name="Admin")
    try:
        update_telegram_lead_message(client_id)
    except Exception as e:
        logger.error(f"Telegram lead update error from CRM comment: {e}")

    return RedirectResponse(
        url="/admin?notice=Mutaxassis+izohi+muvaffaqiyatli+saqlandi#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """
    Telegram bot webhooki:
    1. Guruhdagi tugmalar bosilganda (callback_query)
    2. Lid xabariga 'Reply' (javob) qilib izoh yozilganda (message with reply_to_message)
    """
    try:
        data = await request.json()
        if "callback_query" in data:
            handle_telegram_callback(data)
        elif "message" in data:
            handle_telegram_reply_comment(data)
    except Exception as e:
        logger.error(f"Telegram webhook callback xatoligi: {e}")
    return {"ok": True}

@app.get("/api/clients")
def list_clients():
    """Yig'ilgan barcha mijozlar bazasini JSON ko'rinishida ko'rish"""
    return {"clients": get_all_clients()}

@app.get("/api/clients/csv")
def export_clients_csv():
    """Yig'ilgan mijozlar bazasini Excel / CSV formatida yuklab olish"""
    clients = get_all_clients()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Sarlavhalar
    writer.writerow([
        "ID", "Instagram ID", "Instagram Username", "Instagram Profil Havolasi", "Obuna Holati",
        "Mijoz Ismi", "Telefon raqami", "Yo'nalish", 
        "Manba", "Holati", "Mas'ul xodim", "Mutaxassis Izohi", "💡 AI Ehtiyoj Tahlili",
        "Oxirgi xabar / So'rov", "Yaratilgan vaqti"
    ])
    
    for c in clients:
        uname = c.get("username") or ""
        ig_url = f"https://instagram.com/{uname}" if uname else ""
        is_fol_str = "Obunachi" if c.get("is_follower") else "Obuna emas"
        writer.writerow([
            c.get("id"),
            c.get("instagram_id"),
            f"@{uname}" if uname else "",
            ig_url,
            is_fol_str,
            c.get("full_name"),
            c.get("phone_number"),
            c.get("campaign", "Umumiy"),
            c.get("source", "Direct"),
            c.get("lead_status", "yangi"),
            c.get("manager_name", ""),
            c.get("manager_comment", ""),
            c.get("ai_summary", ""),
            c.get("last_message"),
            c.get("created_at")
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=instagram_mijozlar.csv"}
    )
