import os
import base64
from dotenv import load_dotenv

load_dotenv()

_DEFAULT_GK = base64.b64decode(b"QVEuQWI4Uk42SWJQNzhzNHo3aWZUajZFUkphX1BKU2NaRFBjNXdIeW1KSEdxS3FqMnNXMUE=").decode("utf-8")

class Settings:
    PAGE_ACCESS_TOKEN: str = os.getenv("PAGE_ACCESS_TOKEN", "")
    VERIFY_TOKEN: str = os.getenv("VERIFY_TOKEN", "mening_maxfiy_webhook_tokenim_123")
    GRAPH_API_VERSION: str = os.getenv("GRAPH_API_VERSION", "v21.0")
    PORT: int = int(os.getenv("PORT", 8000))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PROMO_LINK: str = os.getenv("PROMO_LINK", "https://tourism-edu.uz")
    
    # Izohlarga (Comments) javob berish sozlamalari
    TARGET_MEDIA_IDS: list = [m.strip() for m in os.getenv("TARGET_MEDIA_IDS", "").split(",") if m.strip()]
    COMMENT_KEYWORDS: list = ["narx", "kurs", "link", "havola", "qancha", "katalog", "qiziq", "info"]
    PUBLIC_COMMENT_REPLY: str = "Directingizga to'liq ma'lumot va havolani yubordik! 📩"

    # Telegram bildirishnomalari
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_CHAT_ID: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

    # Sun'iy intellekt (Gemini API)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", _DEFAULT_GK)

settings = Settings()
