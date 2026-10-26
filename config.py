import os
import base64
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_DEFAULT_GK = base64.b64decode(b"QVEuQWI4Uk42SWJQNzhzNHo3aWZUajZFUkphX1BKU2NaRFBjNXdIeW1KSEdxS3FqMnNXMUE=").decode("utf-8")
_DEFAULT_PAT = base64.b64decode(b"RUFCRjBFMlRVWkMwQUJTMjJIeDBLdmcxQldHOXE3MzV2S3VVRDBzUkF5ZXRVM2hEdUFtaGczb2J0WkJnSWlQa0k3VXJaQ2QyYkd4NWRaQ1VxSzhjc2pXWkFEWDN6RG1SZUllNm9DbXhRNUNONnE0aWRXSjRxVTB5R2RjS1NrWFRpemFXTVpDZE5UUXg2WWlMc2d0M3pJVkN1YVpBakN6WkNLdGxlYlViSERzcGxNNWFrMm92R0c2MXZlY1BWWVN6R1BWZVpBRXdaRFpE").decode("utf-8")
_DEFAULT_PAGE_TOKEN = base64.b64decode(b"RUFCRjBFMlRVWkMwQUJTejNXdjBTdFMzRU9MRzhFN211UFJic1E2UWYwaGxDZGFoRlEwV1MyaHpCczRDanMxN3VaQmVsdUxCMjRKRHBuWkFhVVdTYVB0blUxQnJtNFlVQmtkanhQSk82Y2V3RVUyTjY4VThndExuT2dhTFpDV3BaQ2NZZmJYeXFaQ0haQXJEZHlyWkJ6ZUFrTU5uWFpBZ2R4NGJJNENHWWlaQWllWkNPTEdlRzJyb3dtWkJHVjFFWkNOUTdmV1pCVUphT3ZhZmJMZQ==").decode("utf-8")

class Settings:
    _raw_pat = os.getenv("PAGE_ACCESS_TOKEN", "").strip()
    PAGE_ACCESS_TOKEN: str = _raw_pat if (_raw_pat and _raw_pat != "YOUR_PAGE_ACCESS_TOKEN_HERE") else _DEFAULT_PAGE_TOKEN
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
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8001530861:AAGHL-4RO3uMnE3ASwWinGP0akLEuUFSGgc")
    TELEGRAM_ADMIN_CHAT_ID: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "-5105674941")

    # Sun'iy intellekt (Gemini API)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", _DEFAULT_GK)

settings = Settings()
