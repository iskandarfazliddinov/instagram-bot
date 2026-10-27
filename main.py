import asyncio
import io
import csv
import os
import logging
import hashlib
import urllib.parse
import time
from collections import OrderedDict
from fastapi import FastAPI, Request, Response, Form, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from starlette.staticfiles import StaticFiles
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
    update_client_manager_comment,
    get_client_by_id,
    append_client_chat_history,
    get_client_chat_history,
    set_client_ai_paused
)
from services.dialog_manager import (
    process_incoming_message,
    process_incoming_comment,
    process_incoming_audio_message,
    process_incoming_video_message
)
from services.instagram import get_recent_media, resolve_media_id_from_url, send_message
from services.admin_view import get_admin_dashboard_html, get_login_page_html
from services.telegram import (
    handle_telegram_callback,
    handle_telegram_reply_comment,
    handle_telegram_private_message,
    update_telegram_lead_message,
    setup_telegram_webhook
)

# Loglarni sozlash
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_followup_and_unresponsive_check():
    """
    Suhbati to'xtab qolganlarga eslatma yuborish va javobsiz qolgan lidlarni Telegram guruhga uzatish
    """
    sent_followups = 0
    sent_unresponsive = 0
    try:
        if get_setting("ai_followup_enabled", "1") == "1":
            try:
                delay_mins = int(get_setting("ai_followup_delay_minutes", "30"))
            except ValueError:
                delay_mins = 30

            from database import (
                get_abandoned_clients,
                get_unresponsive_followup_clients,
                mark_client_followup_sent,
                mark_client_unresponsive_notified,
                get_client_chat_history,
                append_client_chat_history,
                update_client,
                update_client_by_id
            )
            from services.ai_assistant import generate_ai_followup, analyze_lead_need
            from services.instagram import send_message
            from services.telegram import notify_admin_new_lead

            # 1. Suhbat to'xtab qolgan mijozlarga AI orqali aqlli eslatma (Follow-up) yuborish (Faqat Direct ichida)
            abandoned_clients = get_abandoned_clients(min_minutes=delay_mins, max_hours=23)
            for client in abandoned_clients:
                try:
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
                        sent_followups += 1
                        await asyncio.sleep(2)
                except Exception as ab_err:
                    logger.error(f"Mijoz [{client.get('id')}] ga follow-up yuborishda xatolik: {ab_err}")

            # 2. Qat'iy qoida: Telefon raqamini qoldirmagan mijozlar Telegram guruhga UMUMAN yuborilmaydi!
            # Ular faqat CRM jadvalida turadi, guruhga esa faqat raqamini yozgan real lidlar tushadi.
    except Exception as e:
        logger.error(f"Follow-up fon xizmati xatoligi: {e}")
    return {"sent_followups": sent_followups, "sent_unresponsive": sent_unresponsive}

async def follow_up_background_worker():
    """
    Suhbati yakunlanmagan (telefon raqamini qoldirmagan) mijozlarga
    AI orqali avtomatik aqlli eslatma (Follow-up) yuboruvchi xizmat
    """
    await asyncio.sleep(5)  # Server ishga tushgandan so'ng 5 soniya kutish
    while True:
        await run_followup_and_unresponsive_check()
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

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
async def on_startup():
    init_db()
    try:
        setup_telegram_webhook("https://instagram-bot-zohg.onrender.com")
    except Exception as e:
        logger.error(f"Telegram webhook ulashda xatolik: {e}")
    asyncio.create_task(follow_up_background_worker())
    asyncio.create_task(token_auto_refresh_worker())

    # Server ishga tushganda barcha lidlarni kurs va video manbasi bo'yicha boyitish
    async def initial_leads_enrich_and_sync():
        try:
            from services.instagram import enrich_all_leads_campaign_and_source
            cnt = enrich_all_leads_campaign_and_source()
            logger.info(f"Barcha mavjud lidlar video va kurs bo'yicha boyitildi: {cnt} ta yangilandi.")
        except Exception as e:
            logger.error(f"Dastlabki lidlarni boyitishda xatolik: {e}")

        await asyncio.sleep(15)
        try:
            from services.instagram import sync_leads_from_instagram_inbox
            sync_leads_from_instagram_inbox(limit=50)
            logger.info("Instagram Direct yozishmalari bazaga muvaffaqiyatli sinxronlandi.")
        except Exception as e:
            logger.error(f"Dastlabki Instagram sinxronlashda xatolik: {e}")

    asyncio.create_task(initial_leads_enrich_and_sync())
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

# ----------------- TAKRORIY XABARLARNI (DUPLICATE / RETRY) OLDINI OLISH -----------------
PROCESSED_MIDS = OrderedDict()
MAX_MID_CACHE = 5000

def is_duplicate_mid(mid: str) -> bool:
    """
    Meta qayta yuborgan takroriy (retry) xabarlarni filtrlash.
    Meta 5 soniyada javob olmasa bir xil mid bilan xabarni 5-6 marta qayta yuboradi.
    """
    if not mid:
        return False
    now = time.time()
    while PROCESSED_MIDS and (len(PROCESSED_MIDS) > MAX_MID_CACHE or now - next(iter(PROCESSED_MIDS.values())) > 900):
        PROCESSED_MIDS.popitem(last=False)
        
    if mid in PROCESSED_MIDS:
        return True
    PROCESSED_MIDS[mid] = now
    return False

@app.post("/webhook")
async def receive_instagram_events(request: Request, background_tasks: BackgroundTasks):
    """
    Instagram Direct va Videolardagi izohlarni qabul qilish.
    Meta 5 soniyada 200 OK kutadi, shuning uchun barcha og'ir AI va media ishlovlari
    background_tasks da fonda bajariladi, Meta so'rovi esa 10ms ichida 200 OK bilan yakunlanadi.
    Bu xabarlar cheksiz takrorlanib (loop) ketishining oldini oladi.
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
            mid = val.get("message", {}).get("mid")
            if sender_id and msg_text and not is_duplicate_mid(mid):
                logger.info(f"Test xabar keldi [{sender_id}]: {msg_text}")
                background_tasks.add_task(process_incoming_message, sender_id, msg_text)
            return {"status": "ok"}

        for entry in body.get("entry", []):
            entry_id = str(entry.get("id", ""))
            
            # Sahifamizning o'z ID lari (echo va o'zimizdan chiqqan xabarlarni filtrlash uchun)
            PAGE_IDS = {entry_id, "2036629730372506", "39179052008410053", "17841468109131133", "1314546795084427"}
            PAGE_IDS.discard("")

            # 1. Standart Messenger API formati (entry -> messaging)
            for messaging_event in entry.get("messaging", []):
                sender_id = str(messaging_event.get("sender", {}).get("id", ""))
                message = messaging_event.get("message", {})

                # Bot o'zi yuborgan xabarning aks sadosi (echo) yoki sahifamiz nomidan chiqqan xabarlar
                if message.get("is_echo") or (sender_id in PAGE_IDS):
                    continue

                mid = message.get("mid")
                if mid and is_duplicate_mid(mid):
                    logger.info(f"Takroriy xabar (mid={mid}) rad etildi, qayta ishlanmaydi.")
                    continue

                attachments = message.get("attachments") or []
                user_text = (message.get("text") or "").strip()
                quick_reply = message.get("quick_reply", {}).get("payload", "") if message.get("quick_reply") else ""

                # Referral (Instagram Ad orqali kelgan bo'lsa)
                referral = messaging_event.get("referral") or message.get("referral") or {}
                ad_title = ""
                if referral:
                    ad_title = referral.get("ads_context_data", {}).get("ad_title", "") or referral.get("ref", "")

                is_voice = False
                voice_url = ""
                is_video = False
                video_url = ""
                video_title = ad_title

                if attachments:
                    for att in attachments:
                        att_type = att.get("type", "")
                        payload = att.get("payload", {})
                        att_url = payload.get("url", "")
                        att_title = payload.get("title", "")
                        if att_title and not video_title:
                            video_title = att_title

                        logger.info(f"Yangi attachment qabul qilindi [{sender_id}]: type='{att_type}', title='{att_title}', url={att_url[:60] if att_url else 'None'}")

                        # A) Haqiqiy Ovozli xabar (Voice message)
                        # DIQQAT: Faqat va faqat type='audio' yoki type='voice' bo'lganda!
                        # Video, share, reels yoki rasm HECH QACHON ovozli xabar deb hisoblanmaydi!
                        if att_type in ["audio", "voice"]:
                            is_voice = True
                            voice_url = att_url
                            break
                        # B) Video, Reels yoki Ulashilgan video/post (Shared post / video)
                        elif att_type in ["video", "share", "ig_reel"] or (att_url and any(v_ext in att_url.lower() for v_ext in [".mp4", ".mov", ".webm", ".avi"])):
                            is_video = True
                            if not video_url:
                                video_url = att_url

                # Xabarni mos handlerga yo'naltirish:
                # 1. Haqiqiy ovozli xabar
                if is_voice and voice_url:
                    logger.info(f"Yangi Direct OVOZLI xabar keldi [{sender_id}]")
                    background_tasks.add_task(process_incoming_audio_message, sender_id, voice_url)

                # 2. Video yoki Reels yuborilgan / ulashilgan bo'lsa
                elif is_video:
                    logger.info(f"Yangi Direct VIDEO / REELS keldi [{sender_id}]: title='{video_title}', user_text='{user_text}'")
                    background_tasks.add_task(process_incoming_video_message, sender_id, video_title, video_url, user_text)

                # 3. Quick reply tugmasi bosilgan bo'lsa
                elif quick_reply:
                    logger.info(f"Yangi Direct Quick reply keldi [{sender_id}]: {quick_reply}")
                    background_tasks.add_task(process_incoming_message, sender_id, quick_reply)

                # 4. Oddiy matnli xabar
                elif user_text:
                    logger.info(f"Yangi Direct xabar keldi [{sender_id}]: {user_text}")
                    background_tasks.add_task(process_incoming_message, sender_id, user_text)

                # 5. Rasm yoki boshqa fayl biriktirilgan bo'lsa
                elif attachments:
                    att_type = attachments[0].get("type", "")
                    if att_type == "image":
                        logger.info(f"Yangi Direct RASM keldi [{sender_id}]")
                        background_tasks.add_task(process_incoming_message, sender_id, "[Rasm yuborildi]")

            # 2. Yangi Instagram API formati (entry -> changes)
            for change in entry.get("changes", []):
                field = change.get("field")
                value = change.get("value", {})

                # A) Direct xabarlar (Instagram API v26.0)
                if field == "messages":
                    sender_id = str(value.get("sender", {}).get("id", ""))
                    message = value.get("message", {})

                    if message.get("is_echo") or (sender_id in PAGE_IDS):
                        continue

                    mid = message.get("mid")
                    if mid and is_duplicate_mid(mid):
                        logger.info(f"Takroriy xabar (v26.0 mid={mid}) rad etildi, qayta ishlanmaydi.")
                        continue

                    attachments = message.get("attachments") or []
                    user_text = (message.get("text") or "").strip()
                    quick_reply = message.get("quick_reply", {}).get("payload", "") if message.get("quick_reply") else ""

                    # Referral
                    referral = value.get("referral") or message.get("referral") or {}
                    ad_title = ""
                    if referral:
                        ad_title = referral.get("ads_context_data", {}).get("ad_title", "") or referral.get("ref", "")

                    is_voice = False
                    voice_url = ""
                    is_video = False
                    video_url = ""
                    video_title = ad_title

                    if attachments:
                        for att in attachments:
                            att_type = att.get("type", "")
                            payload = att.get("payload", {})
                            att_url = payload.get("url", "")
                            att_title = payload.get("title", "")
                            if att_title and not video_title:
                                video_title = att_title

                            logger.info(f"Yangi attachment (v26.0) qabul qilindi [{sender_id}]: type='{att_type}', title='{att_title}', url={att_url[:60] if att_url else 'None'}")

                            if att_type in ["audio", "voice"]:
                                is_voice = True
                                voice_url = att_url
                                break
                            elif att_type in ["video", "share", "ig_reel"] or (att_url and any(v_ext in att_url.lower() for v_ext in [".mp4", ".mov", ".webm", ".avi"])):
                                is_video = True
                                if not video_url:
                                    video_url = att_url

                    if is_voice and voice_url:
                        logger.info(f"Yangi Direct OVOZLI xabar (v26.0) keldi [{sender_id}]")
                        background_tasks.add_task(process_incoming_audio_message, sender_id, voice_url)
                    elif is_video:
                        logger.info(f"Yangi Direct VIDEO / REELS (v26.0) keldi [{sender_id}]: title='{video_title}', user_text='{user_text}'")
                        background_tasks.add_task(process_incoming_video_message, sender_id, video_title, video_url, user_text)
                    elif quick_reply:
                        logger.info(f"Yangi Direct Quick reply (v26.0) keldi [{sender_id}]: {quick_reply}")
                        background_tasks.add_task(process_incoming_message, sender_id, quick_reply)
                    elif user_text:
                        logger.info(f"Yangi Direct xabar (v26.0) keldi [{sender_id}]: {user_text}")
                        background_tasks.add_task(process_incoming_message, sender_id, user_text)
                    elif attachments:
                        att_type = attachments[0].get("type", "")
                        if att_type == "image":
                            logger.info(f"Yangi Direct RASM (v26.0) keldi [{sender_id}]")
                            background_tasks.add_task(process_incoming_message, sender_id, "[Rasm yuborildi]")

                # B) Video/Reels izohlari
                elif field == "comments":
                    comment_id = value.get("id")
                    comment_text = value.get("text", "")
                    media_id = value.get("media", {}).get("id", "")
                    from_user = value.get("from", {})
                    user_id = from_user.get("id")
                    username = from_user.get("username", "")

                    if comment_id and user_id:
                        if is_duplicate_mid(f"cmt_{comment_id}"):
                            continue
                        background_tasks.add_task(
                            process_incoming_comment,
                            comment_id=comment_id,
                            media_id=media_id,
                            user_id=user_id,
                            username=username,
                            comment_text=comment_text
                        )

    return {"status": "ok"}

# ----------------- CRM AVTORIZATSIYA VA XAVFSIZLIK -----------------

SECRET_SALT = "xta_crm_secret_session_salt_2026_secure"

def make_session_token(user_id: int, role: str, username: str, display_name: str) -> str:
    import base64
    payload = f"{user_id}:{role}:{username}:{display_name}"
    sig = hashlib.sha256(f"{payload}:{SECRET_SALT}".encode()).hexdigest()
    raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode()

def parse_session_token(token: str) -> dict | None:
    if not token:
        return None
    import base64
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.split(":")
        if len(parts) == 5:
            uid, role, username, display_name, sig = parts
            expected_sig = hashlib.sha256(f"{uid}:{role}:{username}:{display_name}:{SECRET_SALT}".encode()).hexdigest()
            if sig == expected_sig:
                return {
                    "id": int(uid),
                    "role": role,
                    "username": username,
                    "display_name": display_name
                }
    except Exception:
        pass

    # Legacy fallback for old tokens
    admin_pwd = get_setting("admin_password", "admin").strip()
    if token == hashlib.sha256(f"admin_{admin_pwd}_crm_salt_2026".encode()).hexdigest() or \
       token == hashlib.sha256(f"{admin_pwd}_crm_salt_2026".encode()).hexdigest():
        return {"id": 0, "role": "admin", "username": "admin", "display_name": "Admin"}

    oper_pwd = get_setting("operator_password", "operator123").strip()
    if token == hashlib.sha256(f"operator_{oper_pwd}_crm_salt_2026".encode()).hexdigest():
        return {"id": 1, "role": "operator", "username": "operator", "display_name": "Operator 1"}

    return None

def get_current_user(request: Request) -> dict | None:
    token = request.cookies.get("crm_session")
    return parse_session_token(token)

def get_current_user_role(request: Request) -> str | None:
    user = get_current_user(request)
    return user["role"] if user else None

def is_authenticated(request: Request) -> bool:
    return get_current_user(request) is not None

def is_admin(request: Request) -> bool:
    user = get_current_user(request)
    return bool(user and user.get("role") == "admin")

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
    """Login va parolni tekshirib sessiya o'rnatish (Admin yoki ko'p operatorlar)"""
    u = username.strip()
    p = password.strip()
    admin_user = get_setting("admin_username", "admin").strip()
    admin_pwd = get_setting("admin_password", "admin").strip()

    # 1. Admin tekshiruvi
    if u.lower() == admin_user.lower() and p == admin_pwd:
        resp = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
        token = make_session_token(0, "admin", admin_user, "Admin")
        resp.set_cookie(key="crm_session", value=token, max_age=86400 * 30, httponly=True, samesite="lax")
        return resp

    # 2. Operatorlar bazasidan tekshirish
    from database import get_operator_by_username, verify_operator_password, update_operator
    op = get_operator_by_username(u)
    if op:
        if not op.get("is_active", 1):
            return RedirectResponse(
                url="/login?error=Ushbu+operator+akkounti+faolsizlantirilgan.+Administratorga+murojaat+qiling.",
                status_code=status.HTTP_303_SEE_OTHER
            )
        if verify_operator_password(op.get("password_hash", ""), p):
            from datetime import datetime
            now_dt_str = datetime.now().strftime("%d.%m.%Y %H:%M")
            update_operator(op["id"], last_login=now_dt_str)
            resp = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
            disp_name = op.get("display_name") or op["username"]
            token = make_session_token(op["id"], "operator", op["username"], disp_name)
            resp.set_cookie(key="crm_session", value=token, max_age=86400 * 30, httponly=True, samesite="lax")
            return resp

    # 3. Zaxira: eski operator_password
    oper_user = get_setting("operator_username", "operator").strip()
    oper_pwd = get_setting("operator_password", "operator123").strip()
    if u.lower() == oper_user.lower() and p == oper_pwd:
        resp = RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
        token = make_session_token(1, "operator", oper_user, "Operator 1")
        resp.set_cookie(key="crm_session", value=token, max_age=86400 * 30, httponly=True, samesite="lax")
        return resp

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
    curr_user = get_current_user(request)
    if not curr_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    settings_data = get_all_settings()
    campaigns_data = get_all_campaigns()
    clients_data = get_all_clients()
    recent_media = get_recent_media(limit=25)
    from database import get_all_operators
    operators_data = get_all_operators()

    html_content = get_admin_dashboard_html(
        settings_data, campaigns_data, clients_data,
        recent_media=recent_media, notice=notice,
        user_role=curr_user["role"],
        current_user=curr_user,
        operators=operators_data
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
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Faqat+Admin+uchun#templates", status_code=status.HTTP_303_SEE_OTHER)

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
    if not is_admin(request):
        return {"ok": False, "error": "Ruxsat berilmagan (Faqat Admin uchun)"}
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
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Faqat+Admin+uchun#campaigns", status_code=status.HTTP_303_SEE_OTHER)

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
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Faqat+Admin+uchun#campaigns", status_code=status.HTTP_303_SEE_OTHER)

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
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Faqat+Admin+uchun#ai", status_code=status.HTTP_303_SEE_OTHER)

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
    """Admin CRM login va parolini yangilash"""
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Faqat+Admin+uchun#security", status_code=status.HTTP_303_SEE_OTHER)

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
        url="/admin?notice=Admin+login+va+parol+muvaffaqiyatli+yangilandi#security",
        status_code=status.HTTP_303_SEE_OTHER
    )
    resp.set_cookie(
        key="crm_session",
        value=get_auth_token("admin"),
        httponly=True,
        max_age=86400 * 30,
        samesite="lax"
    )
    return resp

@app.post("/admin/security/operator/save")
def save_operator_security_settings(
    request: Request,
    operator_username: str = Form(...),
    operator_password: str = Form(...)
):
    """Operator akkaunti login va parolini yangilash (Faqat Admin)"""
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Faqat+Admin+uchun#security", status_code=status.HTTP_303_SEE_OTHER)

    if len(operator_password.strip()) < 3:
        return RedirectResponse(
            url="/admin?notice=Xatolik:+Operator+paroli+juda+qisqa#security",
            status_code=status.HTTP_303_SEE_OTHER
        )

    set_setting("operator_username", operator_username.strip())
    set_setting("operator_password", operator_password.strip())

    return RedirectResponse(
        url="/admin?notice=Operator+login+va+paroli+muvaffaqiyatli+yangilandi#security",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/clients/clear")
def clear_clients(request: Request):
    """Barcha test ma'lumotlarini tozalash"""
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Faqat+Admin+uchun#leads", status_code=status.HTTP_303_SEE_OTHER)

    clear_all_clients()
    return RedirectResponse(
        url="/admin?notice=Barcha+test+lidlar+muvaffaqiyatli+tozalandi!#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/clients/{client_id}/delete")
def delete_single_client(client_id: int, request: Request):
    """Bitta lidni o'chirish"""
    if not is_admin(request):
        return RedirectResponse(url="/admin?notice=Xatolik:+Lidni+o%27chirishga+ruxsat+yo%27q#leads", status_code=status.HTTP_303_SEE_OTHER)

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
    manager_name: str = Form(None, alias="manager_name")
):
    """Admin yoki Operator paneldan mijoz holati va mas'ul xodimni to'g'ridan-to'g'ri o'zgartirish"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    effective_manager = (manager_name or "").strip()
    if not effective_manager or effective_manager in ["Admin", "Operator"]:
        effective_manager = user.get("display_name", "Operator")

    from datetime import datetime
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    update_client_by_id(client_id, lead_status=status_val, manager_name=effective_manager, manager_time=now_str)
    
    try:
        update_telegram_lead_message(client_id)
    except Exception as e:
        logger.error(f"Telegram lead update error from CRM status change: {e}")

    # Agar AJAX (Kanban drag-and-drop yoki tezkor ko'chirish) orqali chaqirilgan bo'lsa -> JSON qaytaramiz
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
        return JSONResponse({
            "success": True,
            "client_id": client_id,
            "new_status": status_val,
            "manager_name": effective_manager,
            "manager_time": now_str
        })

    return RedirectResponse(
        url="/admin?notice=Mijoz+holati+muvaffaqiyatli+yangilandi#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/clients/{client_id}/comment")
def update_comment_from_admin(
    client_id: int,
    request: Request,
    comment: str = Form(""),
    status_val: str = Form(None, alias="status"),
    phone_val: str = Form(None, alias="phone"),
    manager_name: str = Form(None, alias="manager_name")
):
    """CRM dan mutaxassis izohi, holati, mas'ul xodimi va telefon raqamini saqlash hamda Telegram guruhidagi xabarni yangilash"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    effective_manager = (manager_name or "").strip()
    if not effective_manager or effective_manager in ["Admin", "Operator"]:
        effective_manager = user.get("display_name", "Operator")

    from datetime import datetime
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    update_data = {
        "manager_comment": (comment or "").strip(),
        "manager_name": effective_manager,
        "manager_time": now_str
    }
    if status_val and status_val.strip():
        update_data["lead_status"] = status_val.strip()
    if phone_val is not None:
        p_clean = phone_val.strip()
        if p_clean and p_clean != "—":
            update_data["phone_number"] = p_clean

    update_client_by_id(client_id, **update_data)
    try:
        update_telegram_lead_message(client_id)
    except Exception as e:
        logger.error(f"Telegram lead update error from CRM comment: {e}")

    return RedirectResponse(
        url="/admin?notice=Mijoz+ma%27lumotlari+va+izohi+muvaffaqiyatli+saqlandi#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )

# ----------------- CRM INSTAGRAM DIRECT CHAT VA AI BOSHQARUVI -----------------

@app.get("/admin/clients/{client_id}/chat")
def get_client_chat(client_id: int, request: Request):
    """Mijozning Direct suhbat tarixi va AI holatini olish"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Avtorizatsiyadan o'tilmagan"}, status_code=401)
    
    client = get_client_by_id(client_id)
    if not client:
        return JSONResponse({"success": False, "error": "Mijoz topilmadi"}, status_code=404)
    
    ig_id = client.get("instagram_id", "")
    history = get_client_chat_history(ig_id) if ig_id else []
    ai_paused = bool(client.get("ai_paused"))

    return JSONResponse({
        "success": True,
        "client_id": client_id,
        "instagram_id": ig_id,
        "username": client.get("username", ""),
        "full_name": client.get("full_name") or "Mijoz",
        "campaign": client.get("campaign") or "Umumiy",
        "ai_paused": ai_paused,
        "chat_history": history
    })

@app.post("/admin/clients/{client_id}/send-message")
def send_direct_message_from_crm(
    client_id: int,
    request: Request,
    message: str = Form(...)
):
    """
    CRM dan mijozning Instagram Directiga xabar yuborish.
    MUHIM: Mutaxassis xabar yuborgan zahoti ushbu mijoz uchun AI avtomatik to'xtatiladi,
    shunda Sun'iy intellekt va inson aralashib ketmaydi!
    """
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Avtorizatsiyadan o'tilmagan"}, status_code=401)

    msg_text = (message or "").strip()
    if not msg_text:
        return JSONResponse({"success": False, "error": "Xabar matni bo'sh bo'lishi mumkin emas"}, status_code=400)

    client = get_client_by_id(client_id)
    if not client:
        return JSONResponse({"success": False, "error": "Mijoz topilmadi"}, status_code=404)

    ig_id = client.get("instagram_id", "")
    if not ig_id:
        return JSONResponse({"success": False, "error": "Mijozning Instagram ID si topilmadi"}, status_code=400)

    # 1. Instagram Graph API orqali xabar yuborish (is_human=True)
    res = send_message(recipient_id=ig_id, text=msg_text, is_human=True)
    if res.get("error"):
        err_msg = str(res.get("error", "Noma'lum xatolik"))
        if "outside of allowed window" in err_msg.lower() or "2534027" in err_msg or "code 10" in err_msg:
            err_msg = "Meta cheklovi: Mijoz oxirgi marta yozganiga 24 soatdan oshgan yoki 7 kunlik xizmat oynasi tugagan."
        return JSONResponse({"success": False, "error": err_msg})

    manager_name = user.get("display_name", "Mutaxassis")
    from datetime import datetime
    now_time = datetime.now().strftime("%H:%M")
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    # 2. Xabarni suhbat tarixiga yozish
    append_client_chat_history(ig_id, role="manager", text=msg_text, manager_name=manager_name)

    # 3. Ushbu mijoz uchun AI ni AVTOMATIK TO'XTATISH (Inson muloqotda, AI aralashmasligi kerak)
    set_client_ai_paused(client_id, paused=True)

    # 4. Mijoz ma'lumotlarini yangilash (last_message, manager_name, ai_paused)
    update_client_by_id(
        client_id,
        last_message=f"Mutaxassis: {msg_text[:60]}",
        manager_name=manager_name,
        manager_time=now_str,
        ai_paused=1
    )

    try:
        update_telegram_lead_message(client_id)
    except Exception:
        pass

    return JSONResponse({
        "success": True,
        "ai_paused": True,
        "sent_message": {
            "role": "manager",
            "text": msg_text,
            "time": now_time,
            "manager": manager_name
        }
    })

@app.post("/admin/clients/{client_id}/toggle-ai")
def toggle_client_ai(
    client_id: int,
    request: Request,
    ai_paused: int = Form(...)
):
    """Mijoz uchun AI javoblarini yoqish yoki to'xtatish"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"success": False, "error": "Avtorizatsiyadan o'tilmagan"}, status_code=401)

    client = get_client_by_id(client_id)
    if not client:
        return JSONResponse({"success": False, "error": "Mijoz topilmadi"}, status_code=404)

    is_paused = bool(ai_paused == 1)
    set_client_ai_paused(client_id, paused=is_paused)

    return JSONResponse({
        "success": True,
        "client_id": client_id,
        "ai_paused": is_paused
    })

# ----------------- ADMIN: OPERATORLAR VA MUTAXASSISLAR BOSHQARUVI -----------------

@app.post("/admin/operators/create")
def admin_create_operator(
    request: Request,
    display_name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    phone: str = Form("")
):
    """Admin tomonidan yangi mutaxassis (operator) qo'shish"""
    if not is_admin(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)

    u = username.strip().lower()
    p = password.strip()
    name = display_name.strip()
    if not u or not p or not name:
        return RedirectResponse(url="/admin?notice=Barcha+majburiy+maydonlarni+to%27ldiring#operators", status_code=status.HTTP_303_SEE_OTHER)

    from database import get_operator_by_username, create_operator
    if u == "admin" or get_operator_by_username(u):
        return RedirectResponse(url="/admin?notice=Bunday+loginli+operator+allaqachon+mavjud!#operators", status_code=status.HTTP_303_SEE_OTHER)

    create_operator(u, p, name, phone=phone.strip(), role="operator")
    return RedirectResponse(
        url=f"/admin?notice=Yangi+operator+{name}+muvaffaqiyatli+qo%27shildi!#operators",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/operators/{op_id}/update-password")
def admin_update_operator_password(
    op_id: int,
    request: Request,
    new_password: str = Form(...)
):
    """Operator parolini admin tomonidan o'zgartirish"""
    if not is_admin(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    p = new_password.strip()
    if not p:
        return RedirectResponse(url="/admin?notice=Parol+bo%27sh+bo%27lishi+mumkin+emas#operators", status_code=status.HTTP_303_SEE_OTHER)
    from database import update_operator
    update_operator(op_id, password=p)
    return RedirectResponse(url="/admin?notice=Operator+paroli+muvaffaqiyatli+yangilandi#operators", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/operators/{op_id}/toggle-status")
def admin_toggle_operator_status(
    op_id: int,
    request: Request
):
    """Operatorni bloklash yoki faollashtirish"""
    if not is_admin(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    from database import get_operator_by_id, update_operator
    op = get_operator_by_id(op_id)
    if op:
        new_st = 0 if op.get("is_active", 1) else 1
        update_operator(op_id, is_active=new_st)
        msg = "Operator+faolsizlantirildi+(bloklandi)" if new_st == 0 else "Operator+qayta+faollashtirildi"
        return RedirectResponse(url=f"/admin?notice={msg}#operators", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/admin#operators", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/operators/{op_id}/delete")
def admin_delete_operator(
    op_id: int,
    request: Request
):
    """Operatorni tizimdan o'chirish"""
    if not is_admin(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    from database import delete_operator
    delete_operator(op_id)
    return RedirectResponse(url="/admin?notice=Operator+muvaffaqiyatli+o%27chirildi#operators", status_code=status.HTTP_303_SEE_OTHER)

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
            msg = data.get("message", {})
            if msg.get("chat", {}).get("type") == "private":
                handle_telegram_private_message(msg)
            else:
                handle_telegram_reply_comment(data)
    except Exception as e:
        logger.error(f"Telegram webhook callback xatoligi: {e}")
    return {"ok": True}

@app.get("/api/token-check")
def token_check_route():
    from services.instagram import get_access_token
    from config import settings
    tok = get_access_token()
    return {
        "token_len": len(tok) if tok else 0,
        "token_prefix": tok[:15] if tok else "",
        "token_suffix": tok[-10:] if tok else "",
        "is_default": tok == settings.PAGE_ACCESS_TOKEN
    }

@app.get("/api/sync-backup")
def sync_backup_route():
    from database import init_db, get_all_clients
    init_db()
    return {"ok": True, "total": len(get_all_clients())}

@app.get("/api/sync-instagram")
def sync_instagram_route():
    from services.instagram import sync_leads_from_instagram_inbox
    from database import get_all_clients
    res = sync_leads_from_instagram_inbox(limit=50)
    return {"ok": True, "result": res, "total": len(get_all_clients())}

@app.post("/admin/sync-instagram")
def sync_instagram_admin_action(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    from services.instagram import sync_leads_from_instagram_inbox
    sync_leads_from_instagram_inbox(limit=50)
    return RedirectResponse(
        url="/admin?notice=Instagram+Direct+yozishmalaridan+barcha+lidlar+muvaffaqiyatli+yangilandi!#leads",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.get("/api/trigger-followup")
async def trigger_followup_route():
    result = await run_followup_and_unresponsive_check()
    return {"ok": True, **result}

@app.get("/api/enrich-leads")
def enrich_leads_api():
    """Barcha lidlarni kurs va video manbasi bo'yicha boyitish"""
    try:
        from services.instagram import enrich_all_leads_campaign_and_source
        updated = enrich_all_leads_campaign_and_source()
        return {"ok": True, "updated": updated, "message": f"{updated} ta lid muvaffaqiyatli boyitildi"}
    except Exception as e:
        logger.error(f"Lidlarni boyitishda xatolik: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/api/clients")
def list_clients():
    """Yig'ilgan barcha mijozlar bazasini JSON ko'rinishida ko'rish"""
    return {"clients": get_all_clients()}

@app.get("/api/clients/excel")
@app.get("/api/clients/xlsx")
def export_clients_excel():
    """Yig'ilgan mijozlar bazasini Microsoft Excel (.xlsx) formatida to'liq formatlangan holda yuklab olish"""
    clients = get_all_clients()
    
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Lidlar Ro'yxati"
        ws.views.sheetView[0].showGridLines = True

        NAVY_HEADER = "1E1B4B"
        WHITE = "FFFFFF"
        ZEBRA_ROW = "F8FAFC"
        BORDER_COLOR = "CBD5E1"

        STATUS_STYLES = {
            "yangi": {"fill": "F3E8FF", "font_color": "6B21A8", "label": "⚪ Yangi"},
            "boshlangich": {"fill": "F3E8FF", "font_color": "6B21A8", "label": "⚪ Yangi"},
            "jarayonda": {"fill": "FEF3C7", "font_color": "92400E", "label": "🟡 Jarayonda"},
            "boglandi": {"fill": "DCFCE7", "font_color": "166534", "label": "🟢 Bog'lanildi"},
            "bog'landi": {"fill": "DCFCE7", "font_color": "166534", "label": "🟢 Bog'lanildi"},
            "oylanyapti": {"fill": "DBEAFE", "font_color": "1E40AF", "label": "💭 O'ylayapti"},
            "o'ylayapti": {"fill": "DBEAFE", "font_color": "1E40AF", "label": "💭 O'ylayapti"},
            "zahira": {"fill": "E0E7FF", "font_color": "3730A3", "label": "📦 Zahira (Keyingi oqim)"},
            "zaxira": {"fill": "E0E7FF", "font_color": "3730A3", "label": "📦 Zahira (Keyingi oqim)"},
            "rad": {"fill": "FEE2E2", "font_color": "991B1B", "label": "🔴 Rad / Ko'tarmadi"}
        }

        COURSE_STYLES = {
            "front_office": {"fill": "FEF3C7", "font_color": "92400E", "label": "💻 Front Office (Onlayn)"},
            "hotel": {"fill": "EEF2FF", "font_color": "3730A3", "label": "🏨 Hotel Operations and Innovation"},
            "gid_qayta": {"fill": "ECFDF5", "font_color": "065F46", "label": "🌍 Gidlik (Qayta tayyorlash)"},
            "gid_malaka": {"fill": "F0FDFA", "font_color": "115E59", "label": "🗺 Gidlik (Malaka oshirish)"},
            "turagent": {"fill": "F0F9FF", "font_color": "0369A1", "label": "✈️ Turagentlik kursi"},
            "turoperator": {"fill": "EFF6FF", "font_color": "1D4ED8", "label": "✈️ Turoperatorlik kursi"},
            "onlayn": {"fill": "FFFBEB", "font_color": "92400E", "label": "💻 Onlayn platforma"},
            "narx": {"fill": "FEF3C7", "font_color": "78350F", "label": "💰 Kurslar narxi"},
            "dastur": {"fill": "FAF5FF", "font_color": "6B21A8", "label": "📄 O'quv dasturi"},
            "konsultatsiya": {"fill": "EFF6FF", "font_color": "1E40AF", "label": "💬 Batafsil konsultatsiya"},
            "umumiy": {"fill": "F1F5F9", "font_color": "334155", "label": "💬 Boshqa"}
        }

        headers = [
            "№", "Sana va Vaqt", "Mijoz Ismi", "Telefon Raqami",
            "Yo'nalish / Kurs", "Manba", "Holati", "Instagram Profili",
            "Obuna", "Oxirgi So'rov / Xabar", "💡 AI Ehtiyoj Tahlili",
            "Mutaxassis Izohi", "Mas'ul Xodim"
        ]
        ws.append(headers)

        thin_border = Border(
            left=Side(style="thin", color=BORDER_COLOR),
            right=Side(style="thin", color=BORDER_COLOR),
            top=Side(style="thin", color=BORDER_COLOR),
            bottom=Side(style="thin", color=BORDER_COLOR)
        )

        header_fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color=WHITE)

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border

        ws.row_dimensions[1].height = 32

        for r_idx, c in enumerate(clients, start=2):
            uname = (c.get("username") or "").strip()
            phone = (c.get("phone_number") or "").strip()
            status_raw = str(c.get("lead_status") or "yangi").strip().lower()
            st_info = STATUS_STYLES.get(status_raw, {"fill": "F3E8FF", "font_color": "6B21A8", "label": "⚪ Yangi"})

            is_fol_str = "⭐ Obunachi" if c.get("is_follower") else "Obuna emas"
            created_at = (c.get("created_at") or "")[:16].replace("T", " ")

            campaign = c.get("campaign", "Umumiy")
            c_low = campaign.lower()
            if "front" in c_low or "housekeeping" in c_low or "tourism-edu" in c_low:
                course_info = COURSE_STYLES["front_office"]
            elif "hotel" in c_low or "operations" in c_low:
                course_info = COURSE_STYLES["hotel"]
            elif "malaka" in c_low:
                course_info = COURSE_STYLES["gid_malaka"]
            elif "gid" in c_low or "ekskurs" in c_low:
                course_info = COURSE_STYLES["gid_qayta"]
            elif "turagent" in c_low:
                course_info = COURSE_STYLES["turagent"]
            elif "turoperator" in c_low:
                course_info = COURSE_STYLES["turoperator"]
            elif "onlayn" in c_low or "online" in c_low:
                course_info = COURSE_STYLES["onlayn"]
            elif "narx" in c_low:
                course_info = COURSE_STYLES["narx"]
            elif "dastur" in c_low:
                course_info = COURSE_STYLES["dastur"]
            elif "konsultatsiya" in c_low or "batafsil" in c_low:
                course_info = COURSE_STYLES["konsultatsiya"]
            else:
                course_info = COURSE_STYLES["umumiy"]

            source = c.get("source", "Direct")
            source_label = "💬 Direct"
            source_url = None
            s_low = str(source).lower()
            if "reel" in s_low or "instagram.com" in s_low or "video" in s_low:
                if "dbm6ein" in s_low:
                    source_label = "🎬 Front Office Reels ↗"
                elif "dezbpoz" in s_low or "derpzsn" in s_low:
                    source_label = "🎬 Hotel Ops Reels ↗"
                elif "dbdpnkl" in s_low:
                    source_label = "🎬 Gidlik Reels ↗"
                elif "dcqteak" in s_low:
                    source_label = "🎬 Turagent Reels ↗"
                elif "dbxj3f" in s_low:
                    source_label = "🎬 Turoperator Reels ↗"
                else:
                    source_label = "🎬 Reels Video ↗"
                import re
                m = re.search(r"https?://[^\s]+", source)
                if m:
                    source_url = m.group(0)

            row_data = [
                c.get("id") or (r_idx - 1),
                created_at if created_at else "—",
                c.get("full_name") or "Kiritilmagan",
                phone if phone else "—",
                course_info["label"],
                source_label,
                st_info["label"],
                f"@{uname}" if uname else "—",
                is_fol_str,
                c.get("last_message") or "—",
                c.get("ai_summary") or "—",
                c.get("manager_comment") or "—",
                c.get("manager_name") or "—"
            ]
            ws.append(row_data)

            row_fill_color = ZEBRA_ROW if r_idx % 2 == 1 else WHITE
            default_fill = PatternFill(start_color=row_fill_color, end_color=row_fill_color, fill_type="solid")
            ws.row_dimensions[r_idx].height = 24

            for c_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=r_idx, column=c_idx)
                cell.border = thin_border
                cell.fill = default_fill
                cell.font = Font(name="Segoe UI", size=10)

                if c_idx in [1, 2, 4, 7, 9]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif c_idx in [10, 11, 12]:
                    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

                # Telefon raqami: qalin shrift va text formati
                if c_idx == 4 and phone:
                    cell.number_format = "@"
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color="0F172A")

                # Kurs ustuni rangli nishoni
                if c_idx == 5:
                    cell.fill = PatternFill(start_color=course_info["fill"], end_color=course_info["fill"], fill_type="solid")
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color=course_info["font_color"])

                # Manba havolasi (Reels bo'lsa)
                if c_idx == 6 and source_url:
                    cell.hyperlink = source_url
                    cell.font = Font(name="Segoe UI", size=10, color="BE185D", underline="single")
                    cell.alignment = Alignment(horizontal="center", vertical="center")

                # Holat (Status) rangi
                if c_idx == 7:
                    cell.fill = PatternFill(start_color=st_info["fill"], end_color=st_info["fill"], fill_type="solid")
                    cell.font = Font(name="Segoe UI", size=10, bold=True, color=st_info["font_color"])

                # Instagram username bosiladigan havola
                if c_idx == 8 and uname:
                    cell.hyperlink = f"https://instagram.com/{uname}"
                    cell.font = Font(name="Segoe UI", size=10, color="0284C7", underline="single")

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        col_widths = {
            "A": 7,   # №
            "B": 18,  # Sana va Vaqt
            "C": 22,  # Mijoz Ismi
            "D": 18,  # Telefon Raqami
            "E": 30,  # Yo'nalish / Kurs
            "F": 20,  # Manba
            "G": 18,  # Holati
            "H": 22,  # Instagram Profili
            "I": 15,  # Obuna
            "J": 38,  # Oxirgi So'rov / Xabar
            "K": 45,  # 💡 AI Ehtiyoj Tahlili
            "L": 30,  # Mutaxassis Izohi
            "M": 18   # Mas'ul Xodim
        }
        for col_letter, width in col_widths.items():
            ws.column_dimensions[col_letter].width = width

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"XTA_Instagram_Lidlar_{time.strftime('%Y%m%d_%H%M')}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Excel yaratishda xatolik: {e}, CSV ga o'tilmoqda")
        return export_clients_csv()

@app.get("/api/clients/csv")
def export_clients_csv():
    """Yig'ilgan mijozlar bazasini Excel / CSV formatida (UTF-8 BOM bilan) yuklab olish"""
    clients = get_all_clients()
    
    output = io.StringIO()
    # Excel uchun UTF-8 BOM qo'shish (harflar va belgilar buzilmasligi uchun)
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    
    # Sarlavhalar
    writer.writerow([
        "ID", "Instagram Username", "Mijoz Ismi", "Telefon raqami", 
        "Yo'nalish / Kurs", "Manba", "Holati", "Obuna Holati", 
        "💡 AI Ehtiyoj Tahlili", "Oxirgi xabar / So'rov", "Mas'ul xodim", 
        "Mutaxassis Izohi", "Yaratilgan vaqti", "Instagram ID", "Instagram Profil Havolasi"
    ])
    
    status_map = {
        "yangi": "⚪ Yangi",
        "jarayonda": "🟡 Jarayonda",
        "boglandi": "🟢 Bog'lanildi",
        "oylanyapti": "💭 O'ylayapti",
        "zahira": "📦 Zahira (Keyingi oqim)",
        "rad": "🔴 Rad / Ko'tarmadi"
    }

    for c in clients:
        uname = c.get("username") or ""
        phone = c.get("phone_number") or ""
        # Excelda telefon raqami eksponentsial songa aylanib ketmasligi uchun formatlash
        phone_formatted = f'="{phone}"' if phone else "—"
        ig_url = f"https://instagram.com/{uname}" if uname else ""
        is_fol_str = "⭐ Obunachi" if c.get("is_follower") else "Obuna emas"
        status_str = status_map.get(c.get("lead_status", "yangi"), c.get("lead_status", "yangi"))
        created_at = (c.get("created_at") or "")[:16].replace("T", " ")

        writer.writerow([
            c.get("id"),
            f"@{uname}" if uname else "—",
            c.get("full_name") or "Kiritilmagan",
            phone_formatted,
            c.get("campaign", "Umumiy"),
            c.get("source", "Direct"),
            status_str,
            is_fol_str,
            (c.get("ai_summary") or "").replace("\n", " "),
            (c.get("last_message") or "").replace("\n", " "),
            c.get("manager_name", ""),
            (c.get("manager_comment") or "").replace("\n", " "),
            created_at,
            c.get("instagram_id"),
            ig_url
        ])
    
    output.seek(0)
    filename = f"instagram_lidlar_{time.strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8-sig')]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
