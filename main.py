import io
import csv
import logging
import urllib.parse
from fastapi import FastAPI, Request, Response, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from config import settings
from database import (
    init_db,
    get_all_clients,
    get_all_settings,
    set_setting,
    get_all_campaigns,
    create_campaign,
    delete_campaign,
    delete_all_clients,
    reset_client
)
from services.dialog_manager import process_incoming_message, process_incoming_comment
from services.instagram import get_recent_media, resolve_media_id_from_url
from services.admin_view import get_admin_dashboard_html

# Loglarni sozlash
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Instagram Automation & Lead Capture API",
    description="Instagram Direct va Video izohlari orqali avtomatik javob berish, havola ulashish va Telegramga lidlarni uzatish tizimi",
    version="1.1.0"
)

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Ma'lumotlar bazasi ishga tushirildi.")

@app.get("/")
def home():
    return {
        "status": "running",
        "service": "Instagram Automation Bot",
        "docs": "/docs",
        "clients_count": len(get_all_clients())
    }

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

# ----------------- ADMIN VA BAZANI KO'RISH -----------------

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, notice: str = ""):
    """Veb admin boshqaruv paneli"""
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
    direct_welcome: str = Form(""),
    ask_phone: str = Form(""),
    final_message: str = Form(""),
    default_promo_link: str = Form("")
):
    """Direct xabar shablonlarini yangilash"""
    if direct_welcome.strip():
        set_setting("direct_welcome", direct_welcome.strip())
    if ask_phone.strip():
        set_setting("ask_phone", ask_phone.strip())
    if final_message.strip():
        set_setting("final_message", final_message.strip())
    if default_promo_link.strip():
        set_setting("default_promo_link", default_promo_link.strip())

    return RedirectResponse(
        url="/admin?notice=Direct+shablonlari+muvaffaqiyatli+saqlandi",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/campaign/create")
async def add_campaign(
    name: str = Form(...),
    video_url: str = Form(""),
    trigger_keyword: str = Form(""),
    public_reply: str = Form(...),
    promo_link: str = Form(...),
    dm_welcome: str = Form("")
):
    """Yangi video qoidasi (aksiyasi) qo'shish (Variant B: Video linki orqali)"""
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
    if media_id:
        msg += f" (Video ID bog'landi)"
    return RedirectResponse(
        url=f"/admin?notice={urllib.parse.quote(msg)}",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/campaign/delete")
async def remove_campaign(campaign_id: int = Form(...)):
    """Video qoidasini o'chirish"""
    delete_campaign(campaign_id)
    return RedirectResponse(
        url="/admin?notice=Video+qoidasi+o%27chirildi",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/ai/save")
async def save_ai_settings(
    ai_enabled: str = Form(None),
    gemini_api_key: str = Form(""),
    ai_system_prompt: str = Form("")
):
    """Sun'iy intellekt (Gemini AI) sozlamalarini saqlash"""
    is_on = "1" if ai_enabled else "0"
    set_setting("ai_enabled", is_on)

    if gemini_api_key.strip():
        set_setting("gemini_api_key", gemini_api_key.strip())
    if ai_system_prompt.strip():
        set_setting("ai_system_prompt", ai_system_prompt.strip())

    msg = "Sun'iy Intellekt sozlamalari muvaffaqiyatli saqlandi!"
    return RedirectResponse(
        url=f"/admin?notice={urllib.parse.quote(msg)}",
        status_code=status.HTTP_303_SEE_OTHER
    )

@app.post("/admin/clients/clear")
def clear_clients():
    """Barcha test mijozlar tarixini tozalash (AIni qaytadan toza boshlash uchun)"""
    delete_all_clients()
    return RedirectResponse(
        url="/admin?notice=Mijozlar+tarixi+tozalandi+(AI+toza+boshlanadi)",
        status_code=status.HTTP_303_SEE_OTHER
    )

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
    writer.writerow(["ID", "Instagram ID", "Ismi", "Telefon raqami", "Manba", "Bosqich", "Oxirgi xabar", "Yaratilgan vaqti"])
    
    for c in clients:
        writer.writerow([
            c.get("id"),
            c.get("instagram_id"),
            c.get("full_name"),
            c.get("phone_number"),
            c.get("source", "Direct"),
            c.get("step"),
            c.get("last_message"),
            c.get("created_at")
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=instagram_mijozlar.csv"}
    )
