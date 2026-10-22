import logging
import time
import requests
from config import settings
from database import get_setting

logger = logging.getLogger(__name__)

def get_graph_base_url(token: str = None) -> str:
    """
    Agar token EAA... yoki EAB... bilan boshlansa (Meta System User / Page token) -> graph.facebook.com
    Agar token IGAA... bilan boshlansa (Instagram User token) -> graph.instagram.com
    """
    tok = (token or get_access_token() or "").strip()
    if tok.startswith("EAA") or tok.startswith("EAB"):
        return f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}"
    return f"https://graph.instagram.com/{settings.GRAPH_API_VERSION}"

def get_graph_messages_url(token: str = None) -> str:
    return f"{get_graph_base_url(token)}/me/messages"

_last_token_alert_time = 0
_cached_raw_token = ""
_cached_resolved_token = ""

def resolve_page_token(tok: str) -> str:
    """
    Agar System User token (EAA/EAB) kiritilgan bo'lsa,
    u orqali Facebook Page Access Tokenini avtomatik olish.
    """
    cleaned = (tok or "").strip()
    if not cleaned.startswith("EAA") and not cleaned.startswith("EAB"):
        return cleaned

    # Avval bevosita Page token ekanligini tekshiramiz
    try:
        url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/me"
        r = requests.get(url, params={"fields": "id,name,instagram_business_account", "access_token": cleaned}, timeout=5)
        if r.status_code == 200 and r.json().get("instagram_business_account"):
            return cleaned
    except Exception:
        pass

    # Agar System User token bo'lsa -> me/accounts dan sahifa tokenini olamiz
    try:
        url_acc = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/me/accounts"
        r_acc = requests.get(url_acc, params={"access_token": cleaned}, timeout=6)
        if r_acc.status_code == 200:
            pages = r_acc.json().get("data", [])
            for page in pages:
                p_tok = page.get("access_token")
                if p_tok:
                    logger.info(f"System User token orqali Page Token muvaffaqiyatli olindi: {page.get('name')}")
                    return p_tok
    except Exception as e:
        logger.warning(f"Page token olishda xatolik: {e}")
    return cleaned

def get_access_token() -> str:
    """
    Ma'lumotlar bazasidagi (CRM sozlamalari) yoki .env / render.yaml dagi tokenni olish
    """
    global _cached_raw_token, _cached_resolved_token
    db_token = get_setting("page_access_token", "").strip()
    raw = db_token if db_token else settings.PAGE_ACCESS_TOKEN.strip()
    if not raw or raw == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        return ""

    if raw == _cached_raw_token and _cached_resolved_token:
        return _cached_resolved_token

    _cached_raw_token = raw
    _cached_resolved_token = resolve_page_token(raw)
    return _cached_resolved_token

def notify_admin_token_error(error_details: str):
    """
    Token eskirgan yoki Meta tomonidan bloklanganda Telegram adminga shoshilinch xabar yuborish
    (Takroriy spamlarni oldini olish uchun har 30 daqiqada ko'pi bilan 1 marta)
    """
    global _last_token_alert_time
    now = time.time()
    if now - _last_token_alert_time > 1800:
        _last_token_alert_time = now
        try:
            from services.telegram import send_telegram_alert
            send_telegram_alert(
                f"🚨 <b>DIQQAT: Instagram Token ishlamayapti!</b>\n\n"
                f"❌ <b>Meta API xatosi:</b> <code>{error_details[:200]}</code>\n\n"
                f"⚠️ Bot mijozlarga avtomatik javob qaytara olmayapti!\n"
                f"Iltimos, Meta for Developers (Instagram Graph API) sahifasidan yangi token oling va CRM Boshqaruv paneliga kiriting."
            )
        except Exception as e:
            logger.error(f"Telegram alert yuborishda xatolik: {e}")

def check_meta_response_for_errors(data: dict):
    """
    Meta API javobini xatoliklarga tekshirish
    """
    if not isinstance(data, dict):
        return
    err = data.get("error")
    if err:
        err_msg = err.get("message", "")
        err_type = err.get("type", "")
        err_code = err.get("code")
        if (
            "API access blocked" in err_msg
            or "OAuthException" in err_type
            or err_code in [190, 200]
            or "access token" in err_msg.lower()
        ):
            logger.critical(f"Meta Access Token xatosi aniqlandi: {err}")
            notify_admin_token_error(err_msg or str(err))

def check_instagram_token(token: str = None) -> dict:
    """
    Token faolligini va qaysi Instagram akkauntiga tegishli ekanligini tekshirish
    (Ham Instagram User tokenlari, ham Meta System User / Page tokenlarini qo'llab-quvvatlaydi)
    """
    tok = token.strip() if token else get_access_token()
    if not tok or tok == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        return {"ok": False, "error": "Token kiritilmagan"}

    # 1. Meta System User / Page Token (EAA... / EAB...)
    if tok.startswith("EAA") or tok.startswith("EAB"):
        try:
            # A) Agar bevosita Page Token bo'lsa
            url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/me"
            r = requests.get(url, params={"fields": "id,name,username,instagram_business_account{id,username,name}", "access_token": tok}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                ig = data.get("instagram_business_account") or {}
                return {
                    "ok": True,
                    "id": ig.get("id") or data.get("id"),
                    "username": ig.get("username") or data.get("name"),
                    "name": ig.get("name") or data.get("name"),
                    "account_type": "BUSINESS (Muddatsiz Meta Page Token)"
                }
            # B) Agar System User Token bo'lsa -> me/accounts orqali tekshiramiz
            url_acc = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/me/accounts"
            r_acc = requests.get(url_acc, params={"fields": "id,name,instagram_business_account{id,username,name}", "access_token": tok}, timeout=8)
            if r_acc.status_code == 200:
                pages = r_acc.json().get("data", [])
                if pages:
                    p = pages[0]
                    ig = p.get("instagram_business_account") or {}
                    return {
                        "ok": True,
                        "id": ig.get("id") or p.get("id"),
                        "username": ig.get("username") or p.get("name"),
                        "name": ig.get("name") or p.get("name"),
                        "account_type": "BUSINESS (Muddatsiz System User Token)"
                    }
            err_msg = r.json().get("error", {}).get("message") if r.status_code != 200 else "Instagram akkaunt topilmadi"
            return {"ok": False, "error": err_msg, "raw": r.text}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # 2. Standart Instagram User Token (IGAA...)
    url = f"{get_graph_base_url(tok)}/me"
    params = {
        "fields": "id,username,name,account_type",
        "access_token": tok
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        data = r.json()
        if r.status_code == 200 and "id" in data:
            return {
                "ok": True,
                "id": data.get("id"),
                "username": data.get("username", ""),
                "name": data.get("name", ""),
                "account_type": data.get("account_type", "")
            }
        else:
            err_msg = data.get("error", {}).get("message", "Noma'lum Meta API xatoligi")
            return {"ok": False, "error": err_msg, "raw": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def refresh_long_lived_token() -> bool:
    """
    Instagram Long-Lived (60 kunlik) tokenni muddati tugamasdan avtomatik uzaytirish (Auto-Refresh)
    """
    current_token = get_access_token()
    if not current_token or not current_token.startswith("IGAA"):
        return False

    url = f"{get_graph_base_url(current_token)}/refresh_access_token"
    params = {
        "grant_type": "ig_refresh_token",
        "access_token": current_token
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if r.status_code == 200 and "access_token" in data:
            new_token = data["access_token"]
            from database import set_setting
            set_setting("page_access_token", new_token)
            logger.info(f"✅ Instagram tokeni avtomatik yana 60 kunga uzaytirildi (expires_in: {data.get('expires_in')}s)!")
            return True
        else:
            logger.warning(f"Tokenni uzaytirishda Meta javobi: {data}")
            return False
    except Exception as e:
        logger.error(f"Tokenni avtomatik yangilashda xatolik: {e}")
        return False

def send_message(recipient_id: str, text: str) -> dict:
    """
    Instagram Direct orqali mijozga xabar yuborish
    """
    token = get_access_token()
    if not token or token == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        logger.warning("PAGE_ACCESS_TOKEN kiritilmagan. Xabar yuborilmadi.")
        return {"error": "PAGE_ACCESS_TOKEN is not configured"}

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(get_graph_messages_url(token), json=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code != 200:
            logger.error(f"Meta API xatoligi ({response.status_code}): {data}")
            check_meta_response_for_errors(data)
        return data
    except Exception as e:
        logger.error(f"Instagram xabar yuborishda xatolik: {e}")
        return {"error": str(e)}

def send_link_button(recipient_id: str, text: str, button_title: str, url: str) -> dict:
    """
    Tugmali havola (Web URL button) yuborish
    """
    token = get_access_token()
    if not token:
        return {"error": "No token"}

    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text,
                    "buttons": [
                        {
                            "type": "web_url",
                            "url": url,
                            "title": button_title
                        }
                    ]
                }
            }
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(get_graph_messages_url(token), json=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code != 200:
            check_meta_response_for_errors(data)
        return data
    except Exception as e:
        logger.error(f"Tugmali havola yuborishda xatolik: {e}")
        return send_message(recipient_id, f"{text}\n\n👉 {url}")

def send_private_reply_to_comment(comment_id: str, text: str) -> dict:
    """
    Videodagi izoh qoldirgan mijozning Directiga avtomatik shaxsiy xabar yuborish
    (Meta Instagram Private Reply to Comment API)
    """
    token = get_access_token()
    if not token:
        return {"error": "No token"}

    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": text}
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(get_graph_messages_url(token), json=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code != 200:
            logger.error(f"Izohga Direct javob yuborishda xatolik: {data}")
            check_meta_response_for_errors(data)
        return data
    except Exception as e:
        logger.error(f"Izohga Direct yuborishda xatolik: {e}")
        return {"error": str(e)}

def reply_public_comment(comment_id: str, text: str) -> dict:
    """
    Videodagi izoh ostiga ommaviy javob yozish (Public reply)
    """
    token = get_access_token()
    if not token:
        return {"error": "No token"}

    url = f"{get_graph_base_url(token)}/{comment_id}/replies"
    payload = {"message": text}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code != 200:
            check_meta_response_for_errors(data)
        return data
    except Exception as e:
        logger.error(f"Izoh ostiga ommaviy javob yozishda xatolik: {e}")
        return {"error": str(e)}

def get_recent_media(limit: int = 25) -> list:
    """
    Instagram akkauntdagi so'nggi video va postlarni olish
    """
    token = get_access_token()
    if not token or token == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        return []

    url = f"{get_graph_base_url(token)}/me/media"
    params = {
        "fields": "id,caption,permalink,media_type,thumbnail_url,timestamp",
        "access_token": token,
        "limit": limit
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            return res.json().get("data", [])
        data = res.json()
        check_meta_response_for_errors(data)
        logger.warning(f"me/media so'rovi xatolik berdi: {res.text}")
    except Exception as e:
        logger.error(f"Instagram media olishda xatolik: {e}")
    return []

def resolve_media_id_from_url(url_or_id: str) -> tuple[str, str]:
    """
    Instagram havolasi (linki) yoki ID sidan media_id va permalinkni aniqlash
    Qaytaradi: (media_id, permalink)
    """
    if not url_or_id:
        return ("", "")

    cleaned = url_or_id.strip()
    if cleaned.isdigit():
        return (cleaned, f"https://www.instagram.com/p/{cleaned}/")

    import re
    match = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", cleaned)
    shortcode = match.group(1) if match else cleaned

    media_list = get_recent_media(limit=50)
    for item in media_list:
        permalink = item.get("permalink", "")
        if shortcode in permalink or item.get("id") == cleaned:
            return (item["id"], permalink)

    return ("", cleaned)

def get_user_profile(instagram_id: str) -> dict:
    """
    Instagram Graph API orqali foydalanuvchining profil ma'lumotlarini (ism, @username, obuna holati) olish
    """
    token = get_access_token()
    if not token or token == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        return {}

    url = f"{get_graph_base_url(token)}/{instagram_id}"
    params = {
        "fields": "name,username,profile_pic,is_user_follow_business",
        "access_token": token
    }
    try:
        res = requests.get(url, params=params, timeout=6)
        if res.status_code == 200:
            return res.json()
        data = res.json()
        check_meta_response_for_errors(data)
        logger.warning(f"get_user_profile API javobi [{res.status_code}]: {res.text}")
    except Exception as e:
        logger.error(f"Instagram profil ma'lumotlarini olishda xatolik: {e}")
    return {}

def get_media_details(media_id: str) -> dict:
    """
    Instagram Graph API orqali video/post tafsilotlarini (caption, permalink, media_type) olish
    """
    token = get_access_token()
    if not media_id or not token:
        return {}

    url = f"{get_graph_base_url(token)}/{media_id}"
    params = {
        "fields": "id,caption,permalink,media_type,timestamp",
        "access_token": token
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            return res.json()
        data = res.json()
        check_meta_response_for_errors(data)
        logger.warning(f"get_media_details API javobi [{res.status_code}]: {res.text}")
    except Exception as e:
        logger.error(f"Instagram media tafsilotlarini olishda xatolik ({media_id}): {e}")
    return {}
