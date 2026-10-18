import os
import sqlite3
from datetime import datetime

# Serverga ko'chirganda ma'lumotlar saqlanib qolishi uchun data papkasi
DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "clients.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Ma'lumotlar bazasi va jadvalni ishga tushirish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instagram_id TEXT UNIQUE NOT NULL,
            full_name TEXT,
            phone_number TEXT,
            source TEXT DEFAULT 'Direct',
            campaign TEXT DEFAULT 'Umumiy',
            step TEXT DEFAULT 'new',
            last_message TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    # Eski jadval bo'lsa yangi ustunlarni xatosiz qo'shish
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN source TEXT DEFAULT 'Direct'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN campaign TEXT DEFAULT 'Umumiy'")
    except sqlite3.OperationalError:
        pass

    # 1. Tizim sozlamalari jadvali (Direct matnlari)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # 2. Har bir video/mavzu uchun maxsus qoidalar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            trigger_keyword TEXT,
            media_id TEXT,
            media_url TEXT,
            public_reply TEXT,
            dm_welcome TEXT,
            promo_link TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE campaigns ADD COLUMN media_url TEXT")
    except sqlite3.OperationalError:
        pass

    # Standart matnlarni tekshirib kiritish
    default_settings = {
        "direct_welcome": "Assalomu alaykum! Xalqaro turizm akademiyasining Samarqand kampusi rasmiy sahifasiga xush kelibsiz. 😊\n\nSizni qiziqtirgan qayta tayyorlash va malaka oshirish kurslari bo'yicha ma'lumot olish uchun, iltimos, ismingizni qoldiring:",
        "ask_phone": "Rahmat, {name}! 🙌\n\nBatafsil o'quv dasturi, qabul shartlari va dars jadvalini yuborishimiz uchun telefon raqamingizni qoldiring (masalan: +998901234567):",
        "final_message": "Katta rahmat! Ma'lumotlaringiz qabul qilindi. ✅\n\nQuyidagi havola orqali akademiyamiz dasturlari bilan batafsil tanishishingiz mumkin:",
        "default_promo_link": "https://tourism-academy.uz",
        "admin_password": "admin",
        "ai_enabled": "1",
        "gemini_api_key": "",
        "ai_system_prompt": (
            "Siz O'zbekiston Respublikasi Prezidentining PQ-350-son qarori asosida tashkil etilgan Xalqaro Turizm Akademiyasi Samarqand kampusining (International Tourism Academy - Samarkand Campus) rasmiy virtual maslahatchisi va qabul koordinatori vazifasini bajarasiz.\n\n"
            "🏢 AKADEMIYA VA FAOLIYAT HAQIDA RASMIY MA'LUMOT:\n"
            "- Tashkilot: Xalqaro Turizm Akademiyasi — Samarqand kampusi (davlat ta'lim muassasasi).\n"
            "- Huquqiy asosi: O'zbekiston Respublikasi Prezidentining 'Butunjahon turizm tashkiloti shafeligida Xalqaro turizm akademiyasi Samarqand kampusi faoliyatini tashkil etish to'g'risida'gi PQ–350-son qarori.\n"
            "- Muassisi: O'zbekiston Respublikasi Turizm qo'mitasi huzuridagi 'Ipak yo'li' turizm va madaniy meros xalqaro universiteti.\n"
            "- Missiyasi: Turizm va mehmondo'stlik industriyasini rivojlantirishga xizmat qiladigan, xalqaro standartlarga mos, amaliy bilim va ko'nikmalarga ega malakali mutaxassislar avlodini shakllantirishdir.\n"
            "- Xalqaro hamkorlik: Ta'lim jarayonida UN Tourism (sobiq UNWTO) tavsiyalari va ilg'or xalqaro tajriba joriy etilgan.\n"
            "- Asosiy faoliyat: Turizm sohasida ishlayotgan va yangi kasb egallamoqchi bo'lgan mutaxassislar uchun qayta tayyorlash va malaka oshirishning zamonaviy modeli.\n\n"
            "👥 AKADEMIYA RAHBARIYATI:\n"
            "- Narzikulov Dilshod Rustamovich — Akademiya direktori\n"
            "- Safarov Bahodirxon Shahriyorovich — Akademik masalalar bo'yicha direktor o'rinbosari\n"
            "- Raxmanov Jasur Ubaydulloevich — Direktor o'rinbosari\n\n"
            "🎓 TA'LIM YO'NALISHLARI:\n"
            "1. Gid-hamroh va gid-ekskursovodlar tayyorlash va malakasini oshirish;\n"
            "2. Mehmonxona xo'jaligi va boshqaruvi (Hotel Management / Front Office / Housekeeping);\n"
            "3. Turoperatorlik va turagentlik xizmatlari;\n"
            "4. Restoran ishi, servis va mehmondo'stlik (F&B Service);\n"
            "5. Turizm menejmenti va zamonaviy raqamli marketing.\n\n"
            "💎 BIZNING QADRIYATLARIMIZ VA AFZALLIKLAR:\n"
            "- Amaliy natija — har bir kurs real ish ko'nikmasini beradi;\n"
            "- Sifat va standartlar — davlat va xalqaro talablar asosida ta'lim;\n"
            "- Bitiruvchilarga rasmiy davlat va xalqaro sertifikat beriladi;\n"
            "- Samarqanddagi nufuzli turizm va mehmonxona obyektlarida bevosita amaliyot;\n"
            "- Ta'lim va real sektor integratsiyasi.\n\n"
            "📍 MANZIL VA ALOQA MA'LUMOTLARI:\n"
            "- Manzil: Samarqand shahar, Bobur Mirzo ko'chasi, 3A\n"
            "- Telefon: +998 (90) 103 30 00\n"
            "- Email: info@tourism-academy.uz\n"
            "- Rasmiy veb-sayt: https://tourism-academy.uz\n"
            "- Onlayn ta'lim platformasi: https://tourism-edu.uz\n\n"
            "🎯 SIZNING ASOSIY MULOQOT QOIDALARINGIZ:\n"
            "1. Tinglovchilarning savollariga aniq, madaniyatli, samimiy va qisqa (2-3 jumla) qilib javob bering.\n"
            "2. Tinglovchi qaysi tilda yozsa (o'zbek yoki rus), shu tilda professional darajada javob bering.\n"
            "3. SALOMLASHISH QOIDASI: Faqat birinchi xabarda salomlashing. Keyingi har bir xabarda qayta-qayta «Assalomu alaykum» yoki «Salom» demang. Darhol to'g'ridan-to'g'ri savolga javob bering.\n"
            "4. Agar kurs narxlari, dars jadvali yoki hujjat topshirish so'ralsa:\n"
            "   'Batafsil o'quv dasturi, qabul shartlari va dars jadvalini sizga yuborishimiz uchun, iltimos, ismingiz va telefon raqamingizni qoldiring 😊' deb muloyimlik bilan raqam so'rang.\n"
            "5. Rasmiy saytimiz (tourism-academy.uz) yoki onlayn platformamiz (tourism-edu.uz) haqida so'ralsa, havolasini bering."
        )
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    conn.commit()
    conn.close()

# Modul yuklanganda bazani avtomatik tayyorlab qo'yish
init_db()

def get_or_create_client(instagram_id: str) -> dict:
    """Mijozni bazadan olish yoki yangi bo'lsa yaratish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE instagram_id = ?", (instagram_id,))
    row = cursor.fetchone()

    now = datetime.now().isoformat()
    if not row:
        cursor.execute(
            "INSERT INTO clients (instagram_id, step, created_at, updated_at) VALUES (?, 'start', ?, ?)",
            (instagram_id, now, now)
        )
        conn.commit()
        cursor.execute("SELECT * FROM clients WHERE instagram_id = ?", (instagram_id,))
        row = cursor.fetchone()

    client_dict = dict(row)
    conn.close()
    return client_dict

def update_client(instagram_id: str, **kwargs):
    """Mijoz ma'lumotlarini (ism, telefon, bosqich) yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    kwargs["updated_at"] = datetime.now().isoformat()
    
    fields = [f"{k} = ?" for k in kwargs.keys()]
    values = list(kwargs.values())
    values.append(instagram_id)
    
    sql = f"UPDATE clients SET {', '.join(fields)} WHERE instagram_id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()

def get_all_clients():
    """Barcha yig'ilgan mijozlar ro'yxatini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ----------------- SOZLAMALAR (SETTINGS) -----------------

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_all_settings() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}

# ----------------- VIDEO AKSIYALARI (CAMPAIGNS) -----------------

def get_all_campaigns():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_campaign(name: str, trigger_keyword: str, media_id: str, media_url: str, public_reply: str, dm_welcome: str, promo_link: str):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO campaigns (name, trigger_keyword, media_id, media_url, public_reply, dm_welcome, promo_link, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (name, trigger_keyword.strip().lower(), media_id.strip(), media_url.strip(), public_reply, dm_welcome, promo_link, now))
    conn.commit()
    conn.close()

def delete_campaign(campaign_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
    conn.commit()
    conn.close()

def match_campaign(media_id: str = "", text: str = "") -> dict:
    """
    Video ID yoki izohdagi kalit so'zga qarab mos keluvchi aksiyani topish
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns WHERE is_active = 1")
    campaigns = [dict(r) for r in cursor.fetchall()]
    conn.close()

    text_lower = text.lower().strip()

    # 1. Avval media_id bo'yicha aniq mos kelishini qidiramiz
    if media_id:
        for c in campaigns:
            if c.get("media_id") and c["media_id"] == media_id:
                kw = (c.get("trigger_keyword") or "").strip().lower()
                # Agar ushbu videoda ma'lum bir kalit so'z ham ko'rsatilgan bo'lsa
                if kw and kw != "*":
                    if kw in text_lower:
                        return c
                else:
                    # Kalit so'z ko'rsatilmagan bo'lsa, ushbu videodagi BARCHA izohlarga javob qaytaradi!
                    return c

    # 2. Kalit so'z bo'yicha qidiramiz (agar videoga bog'lanmagan umumiy aksiya bo'lsa)
    for c in campaigns:
        kw = (c.get("trigger_keyword") or "").strip().lower()
        if kw and kw != "*" and kw in text_lower:
            return c

    return None

