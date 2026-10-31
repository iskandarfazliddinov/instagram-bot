import re
import json
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
        r = requests.get(url, params={"fields": "id,name", "access_token": cleaned}, timeout=5)
        if r.status_code == 200:
            resp_data = r.json()
            if resp_data.get("id") == "1314546795084427" or resp_data.get("name") == "ITASamarkand":
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

    # Zaxiradagi rasmiy Page Token
    from config import _DEFAULT_PAGE_TOKEN
    return _DEFAULT_PAGE_TOKEN if _DEFAULT_PAGE_TOKEN else cleaned

def get_access_token() -> str:
    """
    Ma'lumotlar bazasidagi (CRM sozlamalari) yoki .env / render.yaml dagi tokenni olish
    """
    global _cached_raw_token, _cached_resolved_token
    db_token = get_setting("page_access_token", "").strip()
    raw = db_token if (db_token and len(db_token) > 20) else settings.PAGE_ACCESS_TOKEN.strip()
    if not raw or raw == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        raw = settings.PAGE_ACCESS_TOKEN.strip()

    if raw == _cached_raw_token and _cached_resolved_token:
        return _cached_resolved_token

    _cached_raw_token = raw
    resolved = resolve_page_token(raw)
    if (not resolved or not resolved.startswith("EA")) and settings.PAGE_ACCESS_TOKEN.strip() != raw:
        resolved = resolve_page_token(settings.PAGE_ACCESS_TOKEN.strip())
    _cached_resolved_token = resolved
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
    Meta API javobini haqiqiy Access Token xatoliklariga tekshirish.
    DIQQAT: Meta vaqtincha uzilishi (Code 1: 'An unknown error has occurred'), 
    limitlar yoki foydalanuvchi maxfiylik sozlamalari token xatosi EMAS!
    Faqatgina haqiqiy token eskirgan/bekor qilingan bo'lsa (Code 190) va
    check_instagram_token() ham muvaffaqiyatsiz bo'lsa, adminga xabar yuboriladi.
    """
    if not isinstance(data, dict):
        return
    err = data.get("error")
    if not err:
        return

    err_msg = str(err.get("message", ""))
    err_code = err.get("code")
    err_subcode = err.get("error_subcode")

    # 1. Vaqtinchalik Meta server xatoliklari (Transient / Server errors) - bular token xatosi emas
    if err_code in [1, 2, 4, 17, 32, 100, 368, 613] or "unknown error" in err_msg.lower():
        logger.warning(f"Meta vaqtinchalik xatoligi (Code {err_code}): {err_msg}")
        return

    # 2. Foydalanuvchi o'z Directini yopib qo'ygan yoki bloklagan holatlar (Code 10 yoki 200)
    if err_code in [10, 200] and not any(k in err_msg.lower() for k in ["token", "session"]):
        logger.warning(f"Meta foydalanuvchi cheklovi (Code {err_code}): {err_msg}")
        return

    # 3. Haqiqiy token eskirgan yoki bekor qilinganligini bildiruvchi belgilar
    is_genuine_token_error = (
        err_code == 190
        or err_subcode in [463, 467, 490]
        or any(phrase in err_msg.lower() for phrase in [
            "error validating access token",
            "session has expired",
            "invalid oauth access token",
            "the access token could not be decrypted"
        ])
    )

    if is_genuine_token_error:
        # Shoshilmasdan, tokenni qayta tekshirib ko'ramiz
        token_check = check_instagram_token()
        if token_check.get("ok"):
            logger.info("Meta bir martalik xatolik berdi, lekin token hali ham faol va ishlayapti.")
            return

        logger.critical(f"Haqiqiy Meta Access Token xatosi tasdiqlandi: {err}")
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

def split_message_text(text: str, max_length: int = 900) -> list[str]:
    """Meta Instagram Direct 1000 belgilik cheklovidan oshmasligi uchun xabarni abzaslar bo'yicha bo'laklash"""
    if not text:
        return []
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = []
    current_len = 0

    paragraphs = text.split("\n\n")
    for para in paragraphs:
        if current_len + len(para) + 2 <= max_length:
            current_part.append(para)
            current_len += len(para) + 2
        else:
            if current_part:
                parts.append("\n\n".join(current_part))
                current_part = []
                current_len = 0

            if len(para) > max_length:
                lines = para.split("\n")
                for line in lines:
                    if current_len + len(line) + 1 <= max_length:
                        current_part.append(line)
                        current_len += len(line) + 1
                    else:
                        if current_part:
                            parts.append("\n".join(current_part))
                            current_part = []
                            current_len = 0
                        while len(line) > max_length:
                            parts.append(line[:max_length])
                            line = line[max_length:]
                        if line:
                            current_part.append(line)
                            current_len += len(line) + 1
            else:
                current_part.append(para)
                current_len += len(para) + 2

    if current_part:
        parts.append("\n\n".join(current_part))

    return parts if parts else [text[:max_length]]

def _send_single_message(recipient_id: str, text: str, is_human: bool = False) -> dict:
    """Yagona bo'lak xabarni Meta Graph API orqali yuborish"""
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
            err = data.get("error", {})
            if is_human:
                try:
                    human_payload = {
                        "recipient": {"id": recipient_id},
                        "message": {"text": text},
                        "messaging_type": "MESSAGE_TAG",
                        "tag": "HUMAN_AGENT"
                    }
                    human_resp = requests.post(get_graph_messages_url(token), json=human_payload, headers=headers, timeout=10)
                    if human_resp.status_code == 200:
                        return human_resp.json()
                except Exception:
                    pass

            if err.get("code") in [1, 2] or "unknown error" in str(err.get("message", "")).lower():
                time.sleep(1)
                try:
                    retry_resp = requests.post(get_graph_messages_url(token), json=payload, headers=headers, timeout=10)
                    if retry_resp.status_code == 200:
                        return retry_resp.json()
                    data = retry_resp.json()
                except Exception:
                    pass

            logger.error(f"Meta API xatoligi ({response.status_code}): {data}")
            check_meta_response_for_errors(data)
        return data
    except Exception as e:
        logger.error(f"Instagram xabar yuborishda xatolik: {e}")
        return {"error": str(e)}

def send_message(recipient_id: str, text: str, is_human: bool = False) -> dict:
    """
    Instagram Direct orqali mijozga xabar yuborish (Avtomatik yoki Inson/Mutaxassis orqali).
    Meta 1000 belgilik cheklovidan oshgan xabarlarni avtomatik bo'laklab yuboradi.
    """
    chunks = split_message_text(text, max_length=900)
    if not chunks:
        return {"error": "Empty text"}

    last_res = {}
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.5)
        last_res = _send_single_message(recipient_id, chunk, is_human=is_human)
    return last_res

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
        else:
            new_cid = data.get("id")
            if new_cid:
                try:
                    from database import mark_comment_processed
                    mark_comment_processed(new_cid)
                except Exception:
                    pass
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

def sync_leads_from_instagram_inbox(limit: int = 50, max_pages: int = 15) -> dict:
    """
    Instagram Direct'dagi barcha sahifalardagi yozishmalarni Meta Graph API orqali olib,
    CRM bazasidagi barcha lidlarni to'liq yangilash va tiklash (Auto-recovery with pagination)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from database import (
        get_connection, update_client, get_or_create_client, 
        sync_leads_backup
    )

    from datetime import datetime, timedelta
    page_token = get_access_token()
    if not page_token:
        return {"ok": False, "error": "Token topilmadi"}

    threads = []
    seen_conv_ids = set()
    current_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/me/conversations"
    params = {
        "platform": "instagram",
        "fields": "id,updated_time,participants",
        "limit": limit,
        "access_token": page_token
    }

    # Faqat so'nggi 14 kunlik (target yoqilgandan keyingi) suhbatlarni olish
    cutoff_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    reached_cutoff = False

    pages_fetched = 0
    while current_url and pages_fetched < max_pages and not reached_cutoff:
        try:
            r_conv = requests.get(current_url, params=params if pages_fetched == 0 else None, timeout=12)
            if r_conv.status_code != 200:
                logger.error(f"Instagram conversations xatoligi: {r_conv.text}")
                from config import _DEFAULT_PAGE_TOKEN
                if _DEFAULT_PAGE_TOKEN and page_token != _DEFAULT_PAGE_TOKEN:
                    page_token = _DEFAULT_PAGE_TOKEN
                    if pages_fetched == 0:
                        params["access_token"] = _DEFAULT_PAGE_TOKEN
                        r_conv = requests.get(current_url, params=params, timeout=12)
                    else:
                        r_conv = requests.get(f"{current_url}&access_token={page_token}", timeout=12)
                if r_conv.status_code != 200:
                    break
            
            res_json = r_conv.json()
            batch = res_json.get("data", [])
            if not batch:
                break
            
            for th in batch:
                up_time = (th.get("updated_time") or "")[:10]
                if up_time and up_time < cutoff_date:
                    reached_cutoff = True
                    break
                cid = th.get("id")
                if cid and cid not in seen_conv_ids:
                    seen_conv_ids.add(cid)
                    threads.append(th)
            
            pages_fetched += 1
            current_url = res_json.get("paging", {}).get("next")
            params = None
        except Exception as e:
            logger.error(f"Instagram yozishmalarni yuklashda xatolik (page {pages_fetched}): {e}")
            break

    def fetch_thread_data(th):
        cid = th.get("id")
        parts = th.get("participants", {}).get("data", [])
        user_part = [p for p in parts if p.get("username") != "xalqaro_turizm_akademiyasi"]
        if not user_part:
            return None
        user = user_part[0]
        username = user.get("username", "")
        ig_id = str(user.get("id", ""))
        if not ig_id:
            return None

        m_url = f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/{cid}/messages"
        try:
            r_msg = requests.get(
                m_url, 
                params={"fields": "id,created_time,from,message", "limit": 25, "access_token": page_token}, 
                timeout=8
            )
            if r_msg.status_code != 200:
                return {"ig_id": ig_id, "username": username, "msgs": []}
            msgs = r_msg.json().get("data", [])
            return {"ig_id": ig_id, "username": username, "msgs": msgs}
        except Exception:
            return {"ig_id": ig_id, "username": username, "msgs": []}

    thread_results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_thread_data, th) for th in threads]
        for f in as_completed(futures):
            res = f.result()
            if res:
                thread_results.append(res)

    recovered_count = 0
    for item in thread_results:
        ig_id = item["ig_id"]
        username = item["username"]
        msgs = item["msgs"]

        # Agar foydalanuvchi biror marta ham Directda o'zi yozmagan bo'lsa (faqat bot private reply yoki reklama yuborgan bo'lsa) - CRM ga kiritilmaydi!
        BOT_USERNAMES = {"xalqaro_turizm_akademiyasi", "ita_samarkand", "ita_samarkandita_samarkand", "itasamarkand"}
        user_msgs = [m for m in msgs if (m.get("from", {}).get("username") or "").lower() not in BOT_USERNAMES and (m.get("message") or "").strip()]
        if not user_msgs:
            continue

        msgs.reverse()
        chat_history = []
        phone = None
        full_name = username
        last_msg = ""
        course = None
        source = None
        all_text_combined = ""

        for m in msgs:
            sender_un = m.get("from", {}).get("username", "")
            text = m.get("message", "")
            if not text:
                continue
            role = "assistant" if sender_un == "xalqaro_turizm_akademiyasi" else "user"
            chat_history.append({"role": role, "text": text, "time": m.get("created_time", "")[11:16]})
            all_text_combined += text + " "

            if role == "user":
                last_msg = text
                clean_digits = re.sub(r"\D", "", text)
                if len(clean_digits) == 9 or (len(clean_digits) == 12 and clean_digits.startswith("998")):
                    phone = f"+998{clean_digits}" if len(clean_digits) == 9 else f"+{clean_digits}"
                    name_cand = re.sub(r"[\d\+\(\)\-\.,]", " ", text).strip()
                    if len(name_cand) >= 2 and not any(k in name_cand.lower() for k in ["salom", "rahmat", "assalomu"]):
                        full_name = name_cand

        f_low = all_text_combined.lower()

        # 1. Front Office & Housekeeping (DbM6EinhiZI)
        if any(k in f_low for k in ["front office", "frontoffice", "housekeeping", "tourism-edu.uz", "xona tozalash"]):
            course = "Onlayn ta'lim (Front Office)"
            source = "Reels: https://www.instagram.com/reel/DbM6EinhiZI/"
        # 2. Hotel Operations and Innovation (DeZbpoZtFw0 / DerPZSNNS0F)
        elif any(k in f_low for k in ["hotel operations", "hotel operation", "mehmonxona boshqaruvi", "menejermisiz", "menejer yoki bo'lim"]):
            course = "Hotel Operations and Innovation"
            source = "Reels: https://www.instagram.com/reel/DeZbpoZtFw0/"
        # 3. Gid malaka oshirish
        elif any(k in f_low for k in ["malaka oshirish", "72 soat", "sertifikatim bor", "повышение квалификации"]):
            course = "Gid-ekskursiyachi (Malaka oshirish)"
        # 4. Gid qayta tayyorlash (DbDpNKLKgll)
        elif any(k in f_low for k in ["qayta tayyorla", "professional gid", "gidlik", "гид", "экскурсовод", "beyjik", "diplom va beyjik"]):
            course = "Gid-ekskursiyachi (Qayta tayyorlash)"
            source = "Reels: https://www.instagram.com/reel/DbDpNKLKgll/"
        # 5. Turagentlik (DcQTeaKTBOa)
        elif any(k in f_low for k in ["turagent", "турагент", "1 oylik «turagentlik»"]):
            course = "Turagentlik kursi"
            source = "Reels: https://www.instagram.com/p/DcQTeaKTBOa/"
        # 6. Turoperatorlik (DbXj3F1joxH)
        elif any(k in f_low for k in ["turoperator", "туроператор", "1 oylik «turoperatorlik»"]):
            course = "Turoperatorlik kursi"
            source = "Reels: https://www.instagram.com/p/DbXj3F1joxH/"
        # 7. Umumiy narx so'raganlar
        elif any(k in f_low for k in ["сколько стоит", "narxi qancha", "narx", "стоимость", "to'lov"]):
            course = "Kurslar narxi"
            source = "Direct"
        # 8. Umumiy dastur so'raganlar
        elif any(k in f_low for k in ["dastur", "программ", "reja", "o'quv reja"]):
            course = "O'quv dasturi"
            source = "Direct"
        # 9. Umumiy ma'lumot / konsultatsiya
        elif any(k in f_low for k in ["подробнее", "batafsil", "malumot", "info", "haqida", "kurslar bormi"]):
            course = "Batafsil konsultatsiya"
            source = "Direct"
        else:
            course = "Batafsil konsultatsiya"
            source = "Direct"

        if ig_id == "1773167100618269":
            full_name = "Temirova Iroda"
            phone = "+998956672200"
            course = "Hotel Operations and Innovation"
            source = "Reels: https://www.instagram.com/reel/DeZbpoZtFw0/"
        elif ig_id == "1448672499922524":
            phone = "+998904517877"
            course = "Kurslar narxi"
            source = "Direct"

        client = get_or_create_client(ig_id)
        updates = {}
        if username and (not client.get("username") or client.get("username") == ""):
            updates["username"] = username
        if full_name and full_name != username and (not client.get("full_name") or client.get("full_name") in ["Noma'lum", "None", username]):
            updates["full_name"] = full_name
        if phone and (not client.get("phone_number") or client.get("phone_number") == ""):
            updates["phone_number"] = phone
            if not client.get("lead_status") or client.get("lead_status") == "boshlangich":
                updates["lead_status"] = "yangi"
            updates["step"] = "completed"
        if course and (not client.get("campaign") or client.get("campaign") in ["Umumiy", "", None]):
            updates["campaign"] = course
        if source and (not client.get("source") or client.get("source") in ["Direct", "", None]):
            updates["source"] = source
        if last_msg:
            updates["last_message"] = last_msg
        if chat_history:
            updates["chat_history"] = json.dumps(chat_history, ensure_ascii=False)
        # Prevent unwanted followups to recovered leads
        if client.get("followup_count", 0) == 0:
            updates["followup_count"] = 1
            
        if updates:
            update_client(ig_id, **updates)
            recovered_count += 1

    sync_leads_backup()
    enrich_all_leads_campaign_and_source()
    return {"ok": True, "recovered_count": recovered_count, "total_threads": len(threads)}

def enrich_all_leads_campaign_and_source():
    """
    Barcha lidlarni suhbat tarixi va xabarlariga asoslanib,
    aniq qaysi video va qaysi kursga qiziqqanini aniqlash va bazani boyitish.
    """
    from database import get_all_clients, update_client_by_id, sync_leads_backup
    clients = get_all_clients()
    updated = 0
    
    for c in clients:
        cid = c.get("id")
        cur_camp = str(c.get("campaign") or "Umumiy").strip()
        cur_src = str(c.get("source") or "Direct").strip()
        
        full_text = (c.get("last_message") or "") + " " + (c.get("ai_summary") or "") + " "
        chat = c.get("chat_history")
        if chat:
            try:
                msgs = json.loads(chat) if isinstance(chat, str) else chat
                for m in msgs:
                    full_text += (m.get("text") or "") + " "
            except Exception:
                pass
                
        f_low = full_text.lower()
        
        detected_course = None
        detected_source = None
        
        # 1. Front Office & Housekeeping (DbM6EinhiZI)
        if any(k in f_low for k in ["front office", "frontoffice", "housekeeping", "tourism-edu.uz", "xona tozalash"]):
            detected_course = "Onlayn ta'lim (Front Office)"
            detected_source = "Reels: https://www.instagram.com/reel/DbM6EinhiZI/"
            
        # 2. Hotel Operations and Innovation (DeZbpoZtFw0 / DerPZSNNS0F)
        elif any(k in f_low for k in ["hotel operations", "hotel operation", "mehmonxona boshqaruvi", "menejermisiz", "menejer yoki bo'lim", "derpzsnns0f", "dezbpozttfw0"]):
            detected_course = "Hotel Operations and Innovation"
            detected_source = "Reels: https://www.instagram.com/reel/DeZbpoZtFw0/"
            
        # 3. Gid malaka oshirish
        elif any(k in f_low for k in ["malaka oshirish", "72 soat", "sertifikatim bor", "повышение квалификации"]):
            detected_course = "Gid-ekskursiyachi (Malaka oshirish)"
            
        # 4. Gid qayta tayyorlash (DbDpNKLKgll)
        elif any(k in f_low for k in ["qayta tayyorla", "professional gid", "gidlik", "гид", "экскурсовод", "beyjik", "diplom va beyjik"]):
            detected_course = "Gid-ekskursiyachi (Qayta tayyorlash)"
            detected_source = "Reels: https://www.instagram.com/reel/DbDpNKLKgll/"
            
        # 5. Turagentlik (DcQTeaKTBOa)
        elif any(k in f_low for k in ["turagent", "турагент", "1 oylik «turagentlik»"]):
            detected_course = "Turagentlik kursi"
            detected_source = "Reels: https://www.instagram.com/p/DcQTeaKTBOa/"
            
        # 6. Turoperatorlik (DbXj3F1joxH)
        elif any(k in f_low for k in ["turoperator", "туроператор", "1 oylik «turoperatorlik»"]):
            detected_course = "Turoperatorlik kursi"
            detected_source = "Reels: https://www.instagram.com/p/DbXj3F1joxH/"
            
        # 7. Umumiy narx so'raganlar
        elif any(k in f_low for k in ["сколько стоит", "narxi qancha", "narx", "стоимость", "to'lov"]):
            detected_course = "Kurslar narxi"
            
        # 8. Umumiy dastur so'raganlar
        elif any(k in f_low for k in ["dastur", "программ", "reja", "o'quv reja", "kurs dasturi"]):
            detected_course = "O'quv dasturi"
            
        # 9. Umumiy ma'lumot / konsultatsiya
        elif any(k in f_low for k in ["подробнее", "batafsil", "malumot", "info", "haqida", "kurslar bormi"]):
            detected_course = "Batafsil konsultatsiya"
        else:
            detected_course = "Batafsil konsultatsiya"
            
        updates = {}
        if detected_course:
            if cur_camp in ["Umumiy", "", None] or "Umumiy" in cur_camp:
                updates["campaign"] = detected_course
            elif cur_camp == "Batafsil konsultatsiya" and detected_course != "Batafsil konsultatsiya":
                updates["campaign"] = detected_course
                
        if detected_source and (cur_src in ["Direct", "", None] or not cur_src):
            updates["source"] = detected_source
            
        if updates and cid:
            update_client_by_id(cid, **updates)
            updated += 1
            
    sync_leads_backup()
    return updated
