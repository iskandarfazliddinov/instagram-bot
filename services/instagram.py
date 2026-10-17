import logging
import requests
from config import settings

logger = logging.getLogger(__name__)

GRAPH_API_URL = f"https://graph.instagram.com/{settings.GRAPH_API_VERSION}/me/messages"
GRAPH_BASE_URL = f"https://graph.instagram.com/{settings.GRAPH_API_VERSION}"

def send_message(recipient_id: str, text: str) -> dict:
    """
    Instagram Direct orqali mijozga xabar yuborish
    """
    if not settings.PAGE_ACCESS_TOKEN or settings.PAGE_ACCESS_TOKEN == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        logger.warning("PAGE_ACCESS_TOKEN kiritilmagan. Xabar yuborilmadi.")
        return {"error": "PAGE_ACCESS_TOKEN is not configured"}

    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    headers = {
        "Authorization": f"Bearer {settings.PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(GRAPH_API_URL, json=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code != 200:
            logger.error(f"Meta API xatoligi: {data}")
        return data
    except Exception as e:
        logger.error(f"Instagram xabar yuborishda xatolik: {e}")
        return {"error": str(e)}

def send_link_button(recipient_id: str, text: str, button_title: str, url: str) -> dict:
    """
    Tugmali havola (Web URL button) yuborish
    """
    if not settings.PAGE_ACCESS_TOKEN:
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
        "Authorization": f"Bearer {settings.PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(GRAPH_API_URL, json=payload, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Tugmali havola yuborishda xatolik: {e}")
        # Fallback: oddiy matn sifatida jo'natamiz
        return send_message(recipient_id, f"{text}\n\n👉 {url}")

def send_private_reply_to_comment(comment_id: str, text: str) -> dict:
    """
    Videodagi izoh qoldirgan mijozning Directiga avtomatik shaxsiy xabar yuborish
    (Meta Instagram Private Reply to Comment API)
    """
    if not settings.PAGE_ACCESS_TOKEN:
        return {"error": "No token"}

    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": text}
    }
    headers = {
        "Authorization": f"Bearer {settings.PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(GRAPH_API_URL, json=payload, headers=headers, timeout=10)
        data = response.json()
        if response.status_code != 200:
            logger.error(f"Izohga Direct javob yuborishda xatolik: {data}")
        return data
    except Exception as e:
        logger.error(f"Izohga Direct yuborishda xatolik: {e}")
        return {"error": str(e)}

def reply_public_comment(comment_id: str, text: str) -> dict:
    """
    Videodagi izoh ostiga ommaviy javob yozish (Public reply)
    """
    if not settings.PAGE_ACCESS_TOKEN:
        return {"error": "No token"}

    url = f"{GRAPH_BASE_URL}/{comment_id}/replies"
    payload = {"message": text}
    headers = {
        "Authorization": f"Bearer {settings.PAGE_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Izoh ostiga ommaviy javob yozishda xatolik: {e}")
        return {"error": str(e)}

def get_recent_media(limit: int = 25) -> list:
    """
    Instagram akkauntdagi so'nggi video va postlarni olish
    """
    if not settings.PAGE_ACCESS_TOKEN or settings.PAGE_ACCESS_TOKEN == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        return []

    url = f"{GRAPH_BASE_URL}/me/media"
    params = {
        "fields": "id,caption,permalink,media_type,thumbnail_url,timestamp",
        "access_token": settings.PAGE_ACCESS_TOKEN,
        "limit": limit
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200:
            return res.json().get("data", [])
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
    # 1. Agar to'g'ridan-to'g'ri raqamli ID kiritilgan bo'lsa
    if cleaned.isdigit():
        return (cleaned, f"https://www.instagram.com/p/{cleaned}/")

    # 2. Havoladan shortcode ajratib olish (/reel/SHORTCODE/ yoki /p/SHORTCODE/)
    import re
    match = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]+)", cleaned)
    shortcode = match.group(1) if match else cleaned

    # Instagram API orqali media ro'yxatidan qidirish
    media_list = get_recent_media(limit=50)
    for item in media_list:
        permalink = item.get("permalink", "")
        if shortcode in permalink or item.get("id") == cleaned:
            return (item["id"], permalink)

    # Agar topilmasa ham shortcode/linkni qaytaramiz
    return ("", cleaned)


