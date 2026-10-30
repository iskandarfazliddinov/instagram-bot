import os
import re
import json
import sqlite3
from datetime import datetime, timezone, timedelta

# O'zbekiston vaqti (Toshkent / Samarqand: UTC+5)
UZB_TZ = timezone(timedelta(hours=5))

def now_uzb() -> datetime:
    """O'zbekiston vaqti (UTC+5) bo'yicha joriy datetime"""
    return datetime.now(UZB_TZ)

def now_uzb_iso() -> str:
    """O'zbekiston vaqti bo'yicha ISO 8601 formati"""
    return datetime.now(UZB_TZ).isoformat()

def now_uzb_str() -> str:
    """O'zbekiston vaqti bo'yicha 'DD.MM.YYYY HH:MM' formati"""
    return datetime.now(UZB_TZ).strftime("%d.%m.%Y %H:%M")

def now_uzb_date() -> str:
    """O'zbekiston vaqti bo'yicha 'YYYY-MM-DD' formati"""
    return datetime.now(UZB_TZ).strftime("%Y-%m-%d")

def now_uzb_time() -> str:
    """O'zbekiston vaqti bo'yicha 'HH:MM' formati"""
    return datetime.now(UZB_TZ).strftime("%H:%M")

def to_uzb_time_str(dt_val) -> str:
    """Har qanday vaqt qiymatini O'zbekiston (UTC+5) formatiga ('DD.MM.YYYY HH:MM') o'tkazish"""
    if not dt_val or dt_val in ["—", "None", "null", ""]:
        return "—"
    try:
        s = str(dt_val).strip()
        # Agar allaqachon DD.MM.YYYY formatida bo'lsa
        if len(s) >= 10 and s[2] == '.' and s[5] == '.':
            return s[:16]
        if "T" in s or "-" in s:
            clean_s = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_s)
            if dt.tzinfo is None:
                # SQLite CURRENT_TIMESTAMP UTC da bo'ladi
                dt = dt.replace(tzinfo=timezone.utc).astimezone(UZB_TZ)
            else:
                dt = dt.astimezone(UZB_TZ)
            return dt.strftime("%d.%m.%Y %H:%M")
        return s[:16]
    except Exception:
        return str(dt_val)[:16]

import base64

# Serverga ko'chirganda ma'lumotlar saqlanib qolishi uchun data papkasi
DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "clients.db")
BACKUP_FILE = os.path.join(DB_DIR, "leads_backup.json")
SETTINGS_BACKUP_FILE = os.path.join(DB_DIR, "settings_backup.json")
OPERATORS_BACKUP_FILE = os.path.join(DB_DIR, "operators_backup.json")
ACTIVITY_LOGS_BACKUP_FILE = os.path.join(DB_DIR, "activity_logs_backup.json")
_DEFAULT_GK = base64.b64decode(b"QVEuQWI4Uk42SWJQNzhzNHo3aWZUajZFUkphX1BKU2NaRFBjNXdIeW1KSEdxS3FqMnNXMUE=").decode("utf-8")
DEFAULT_GEMINI_KEY = os.getenv("GEMINI_API_KEY", _DEFAULT_GK)

def hash_operator_password(password: str) -> str:
    import hashlib
    return hashlib.sha256(f"{password}_salt_xta_2026".encode()).hexdigest()

def verify_operator_password(stored_hash: str, password: str) -> bool:
    if not stored_hash:
        return False
    return stored_hash == hash_operator_password(password) or stored_hash == password

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
    # Jadval ustunlarini xatosiz qo'shish (migratsiya)
    for col, col_type in [
        ("source", "TEXT DEFAULT 'Direct'"),
        ("campaign", "TEXT DEFAULT 'Umumiy'"),
        ("lead_status", "TEXT DEFAULT 'yangi'"),
        ("manager_name", "TEXT DEFAULT ''"),
        ("manager_time", "TEXT DEFAULT ''"),
        ("tg_message_id", "INTEGER"),
        ("username", "TEXT DEFAULT ''"),
        ("profile_pic", "TEXT DEFAULT ''"),
        ("is_follower", "INTEGER DEFAULT 0"),
        ("ai_summary", "TEXT DEFAULT ''"),
        ("manager_comment", "TEXT DEFAULT ''"),
        ("chat_history", "TEXT DEFAULT '[]'"),
        ("followup_count", "INTEGER DEFAULT 0"),
        ("last_followup_at", "TEXT DEFAULT ''"),
        ("ai_paused", "INTEGER DEFAULT 0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE clients ADD COLUMN {col} {col_type}")
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

    # 3. Qayta ishlov berilgan izohlar jadvali (bir izohga faqat 1 marta javob berish va takrorlanishni to'xtatish uchun)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_comments (
            comment_id TEXT PRIMARY KEY,
            created_at TIMESTAMP
        )
    """)

    # 4. Mutaxassislar (Operatorlar) jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            role TEXT DEFAULT 'operator',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            allowed_directions TEXT DEFAULT 'all'
        )
    """)
    try:
        cursor.execute("ALTER TABLE operators ADD COLUMN allowed_directions TEXT DEFAULT 'all'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("UPDATE clients SET lead_status = 'boglandi' WHERE lead_status = 'jarayonda'")
    except Exception:
        pass

    # 5. Xodimlar faoliyat jurnali (Audit & Anti-Fraud logs)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            operator_name TEXT,
            action_type TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. Javob kutilayotgan izohlar jadvali (Faqat izoh qoldirgan, lekin hali Directda javob bermaganlar)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_comments (
            instagram_id TEXT PRIMARY KEY,
            comment_id TEXT,
            media_id TEXT,
            source TEXT,
            campaign TEXT,
            comment_text TEXT,
            dm_welcome_text TEXT,
            username TEXT DEFAULT '',
            created_at TIMESTAMP
        )
    """)

    # Tarixiy faqat izoh qoldirib, hali Directda biror marta javob yozmaganlarni pending_comments ga o'tkazish va clients dan tozalash
    try:
        cursor.execute("SELECT id, instagram_id, username, last_message, chat_history, source, campaign, phone_number, created_at FROM clients")
        rows = cursor.fetchall()
        for r in rows:
            cid, ig_id, uname, lmsg, ch_raw, src, camp, phone, c_time = r
            has_phone = bool(phone and str(phone).strip() not in ['', '—', 'None', 'null'])
            ch = json.loads(ch_raw) if ch_raw else []
            has_real_reply = any(m.get('role') == 'user' and not m.get('text', '').startswith('[Video izohi]:') for m in ch)
            if not has_phone and not has_real_reply and str(lmsg).startswith('Izoh:'):
                clean_comment = str(lmsg).replace('Izoh:', '').strip().strip('«»').split('(')[0].strip()
                cursor.execute("""
                    INSERT OR REPLACE INTO pending_comments (instagram_id, source, campaign, comment_text, username, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ig_id, src, camp, clean_comment, uname or '', c_time))
                cursor.execute("DELETE FROM clients WHERE id = ?", (cid,))
        conn.commit()
    except Exception:
        pass

    # Standart matnlarni tekshirib kiritish
    default_settings = {
        "direct_welcome": "Assalomu alaykum! Xalqaro turizm akademiyasining Samarqand kampusi rasmiy sahifasiga xush kelibsiz. 😊\n\nSizni qiziqtirgan qayta tayyorlash va malaka oshirish kurslari bo'yicha ma'lumot olish uchun, iltimos, ismingizni qoldiring:",
        "ask_phone": "Rahmat, {name}! 🙌\n\nBatafsil o'quv dasturi, qabul shartlari va dars jadvalini yuborishimiz uchun telefon raqamingizni qoldiring (masalan: +998901234567):",
        "final_message": "Rahmat, tez orada siz bilan bog'lanamiz! 😊\n\nQuyidagi havola orqali akademiyamiz platformasidagi ta'lim yo'nalishlari bilan batafsil tanishishingiz mumkin:",
        "default_promo_link": "https://tourism-edu.uz",
        "admin_username": "admin",
        "admin_password": "Isak2002",
        "operator_username": "operator",
        "operator_password": "operator123",
        "ai_enabled": "1",
        "ai_followup_enabled": "0",
        "ai_followup_delay_minutes": "30",
        "gemini_api_key": DEFAULT_GEMINI_KEY,
        "ai_system_prompt": (
            "Siz O'zbekiston Respublikasi Prezidentining PQ-350-son qarori asosida tashkil etilgan Xalqaro Turizm Akademiyasi Samarqand kampusining (International Tourism Academy - Samarkand Campus) rasmiy virtual maslahatchisi va qabul koordinatori vazifasini bajarasiz.\n\n"
            "🏢 AKADEMIYA VA FAOLIYAT HAQIDA RASMIY MA'LUMOT:\n"
            "- Tashkilot: Xalqaro Turizm Akademiyasi — Samarqand kampusi (davlat ta'lim muassasasi shaklidagi yuridik shaxs).\n"
            "- Huquqiy asosi: O'zbekiston Respublikasi Prezidentining 'Butunjahon turizm tashkiloti shafeligida Xalqaro turizm akademiyasi Samarqand kampusi faoliyatini tashkil etish to'g'risida'gi PQ–350-son qarori.\n"
            "- Muassisi: O'zbekiston Respublikasi Turizm qo'mitasi huzuridagi 'Ipak yo'li' turizm va madaniy meros xalqaro universiteti.\n"
            "- Missiyasi: Turizm va mehmondo'stlik industriyasini rivojlantirishga xizmat qiladigan, xalqaro standartlarga mos, amaliy bilim va ko'nikmalarga ega malakali mutaxassislar avlodini shakllantirishdir.\n"
            "- Xalqaro hamkorlik: UN Tourism (sobiq UNWTO) tavsiyalari va ilg'or xalqaro ta'lim tajribasi.\n\n"
            "📍 MANZIL VA ALOQA MA'LUMOTLARI:\n"
            "- Manzil: Samarqand shahar, Bobur Mirzo ko'chasi, 3A (Xalqaro turizm akademiyasi Samarqand kampusi)\n"
            "- Telefon / Aloqa: +998 (90) 103-30-00\n"
            "- Email: info@tourism-edu.uz\n"
            "- Rasmiy veb-sayt va onlayn ta'lim platformasi: https://tourism-edu.uz\n\n"
            "══════════════════════════════════════════════════════════════\n"
            "🎓 QABUL BOSHLANGAN RASMIY KURSLAR VA ANIQ MA'LUMOTLAR:\n"
            "══════════════════════════════════════════════════════════════\n\n"
            "1. 🗺 GID-EKSKURSIYACHI QAYTA TAYYORLASH KURSI 🌍\n"
            "• Kimlar uchun: Turizm sohasida yangi kasb egallashni, professional gid-ekskursiyachi bo'lishni va O'zbekistonning eng mashhur turistik shaharlarida faoliyat yuritishni xohlovchilar uchun (noldan yangi kasb egallovchilar).\n"
            "• Kurs davomiyligi: 4 oy.\n"
            "• O'quv dasturi: Gid-ekskursiyachi sifatida ishlash uchun zarur bo'lgan chuqur nazariy bilim va amaliy ko'nikmalar, mashhur turistik obidalar bo'yicha amaliy ekskursiyalar.\n"
            "• Beriladigan rasmiy hujjatlar:\n"
            "  - Kursni muvaffaqiyatli tamomlagandan so'ng rasmiy Qayta tayyorlash diplomi beriladi.\n"
            "  - Professional beyjik taqdim etiladi. Ushbu beyjik orqali butun O'zbekiston bo'ylab (Toshkent, Samarqand, Buxoro, Xiva, Shahrisabz va boshqalar) qonuniy va erkin gid sifatida faoliyat yuritish imkoniyati beriladi.\n"
            "• Karyera imkoniyatlari: Professional gid-ekskursiyachi sifatida ishlash, mahalliy va xorijiy sayyohlarga ekskursiyalar o'tkazish, turizmda o'z karyerasini boshlash, doimiy daromad va yangi imkoniyatlar.\n"
            "• O'qish narxi: 5 500 000 so'm.\n"
            "• Manzil: Samarqand shahar, Bobur Mirzo 3A.\n"
            "• Aloqa uchun: +998 (90) 103-30-00.\n\n"
            "2. 🗺 GID-EKSKURSIYACHILAR UCHUN MALAKA OSHIRISH KURSI ✨\n"
            "• Kimlar uchun: Amaldagi gid-ekskursiyachilar; sertifikatining amal qilish muddati tugagan gidlar; kasbiy bilim va amaliy ko'nikmalarini yangilashni istagan soha mutaxassislari.\n"
            "• Kurs davomiyligi: 1 oy (72 soat).\n"
            "• Kurs davomida:\n"
            "  - Turizm sohasidagi bilimlarni yangilash;\n"
            "  - Gidlik faoliyati bo'yicha kasbiy malakani oshirish;\n"
            "  - Ekskursiyalarni tashkil etish va o'tkazish bo'yicha bilimlarni mustahkamlash;\n"
            "  - Zamonaviy turizm tendensiyalariga mos kasbiy mahoratni rivojlantirish.\n"
            "• Beriladigan rasmiy hujjat: Kursni muvaffaqiyatli tamomlagan tinglovchilarga belgilangan tartibda rasmiy hujjat (malaka oshirish sertifikati) taqdim etiladi.\n"
            "• O'qish narxi: 2 350 000 so'm.\n"
            "• Manzil: Samarqand kampusi, Bobur Mirzo 3A.\n"
            "• Aloqa uchun: +998 (90) 103-30-00.\n\n"
            "3. 🌍 TURAGENTLIK KURSI 🚀\n"
            "• Kimlar uchun: Yangi kasb egallash va turizm sohasida o'z faoliyatini boshlashni yoki shaxsiy turagentligini ochishni xohlovchilar uchun.\n"
            "• Kurs davomiyligi: 1 oy.\n"
            "• O'quv dasturi: Turagentlik sohasida ishlash uchun zarur bo'lgan barcha bilim va amaliy ko'nikmalar.\n"
            "• Beriladigan rasmiy hujjat: Kurs yakunida rasmiy sertifikat beriladi.\n"
            "• Karyera imkoniyatlari: Turagentlik kompaniyalarida ishlash, turizmda professional karyera boshlash, kelajakda o'z shaxsiy turagentligini ochish.\n"
            "• O'qish narxi: 2 350 000 so'm.\n\n"
            "4. 🌍 TUROPERATORLIK KURSI 🚀\n"
            "• Kimlar uchun: Yangi kasb egallash va turizm sohasida turoperator sifatida faoliyat boshlashni xohlovchilar uchun.\n"
            "• Kurs davomiyligi: 1 oy.\n"
            "• O'quv dasturi: Turoperatorlik sohasida ishlash uchun zarur bilim va amaliy ko'nikmalar, turistik yo'nalishlar va sayohat paketlarini shakllantirish, logistika.\n"
            "• Beriladigan rasmiy hujjat: Kurs yakunida rasmiy sertifikat beriladi.\n"
            "• Karyera imkoniyatlari: Turoperator kompaniyalarida ishlash, turizmda karyera boshlash, mustaqil sayohat paketlarini shakllantirish, o'z turoperatorlik faoliyatini yo'lga qo'yish.\n"
            "• O'qish narxi: 2 350 000 so'm.\n\n"
            "5. 💻 RASMIY ONLAYN TA'LIM PLATFORMASI VA MOBIL ILOVA: https://tourism-edu.uz\n"
            "• Rasmiy platforma: https://tourism-edu.uz\n"
            "• Mobil ilovalar: App Store va Google Play orqali yuklab olish mumkin.\n"
            "• Platformada mavjud onlayn kurslar:\n"
            "  1) 🛎 Front Office (Qabul va joylashtirish bo'limi):\n"
            "     - Mehmonxona sohasi bo'yicha kirish, Front Office roli va vazifalari;\n"
            "     - Mehmonlarni kutib olish, joylashtirish (Check-in) va kuzatish (Check-out) jarayonlari;\n"
            "     - Bron qilish (Reservation) tizimi bilan ishlash, xonalar fondi boshqaruvi;\n"
            "     - Mehmonlar bilan muloqot etikasi, xalqaro servis standartlari, muammoli vaziyatlarni hal qilish;\n"
            "     - Mehmonxonada to'lovlar, hisob-kitoblar va kassa operatsiyalari.\n"
            "  2) 🛏 Housekeeping (Mehmonxona xo'jaligi):\n"
            "     - Mehmonxona xo'jaligi tuzilmasi, xizmat ko'rsatish standartlari;\n"
            "     - Xonalar tozaligi, sanitariya-gigiyena qoidalari, dezinfeksiya;\n"
            "     - Tozalash vositalari va professional uskunalardan to'g'ri foydalanish;\n"
            "     - Choyshablar, yuvish (laundry), xona anjomlarini to'ldirish (minibar, gigiyena vositalari);\n"
            "     - Mehmonlar xavfsizligi, yo'qolgan buyumlar (Lost & Found) tartibi.\n"
            "• Qulayliklari: Video darslar, amaliy topshiriqlar, testlar. Smartfon yoki kompyuter orqali istalgan joydan masofaviy o'qish imkoniyati.\n"
            "• Beriladigan hujjat: Platformada o'qib tamomlagandan so'ng QR-kodli rasmiy sertifikat beriladi!\n\n"
            "6. 🏨 «HOTEL OPERATIONS AND INNOVATION 2026–2027» DASTURI:\n"
            "• Tashkilotchi: UN Tourism va Xalqaro Turizm Akademiyasi Samarqand kampusi.\n"
            "• Kimlar uchun: Mehmonxona sohasi rahbarlari (menejerlar, bo'lim boshliqlari, supervayzerlar).\n"
            "• Dastur: 7 ta moduldan iborat nufuzli xalqaro qayta tayyorlash dasturi (Banqueting, Front Office, Housekeeping, F&B, Maintenance, Safety & Crisis, Revenue Management).\n"
            "• PDF reja Telegram bot orqali: https://t.me/MyMarketingAndPrBot?start=hotel\n"
            "• PDF reja to'g'ridan-to'g'ri havola: https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n"
            "• Ariza topshirish (Zoho form): https://survey.zohopublic.com/zs/jQCZao\n\n"
            "══════════════════════════════════════════════════════════════\n"
            "🎯 SIZNING ASOSIY MULOQOT VA JAVOB BERISH QOIDALARINGIZ:\n"
            "══════════════════════════════════════════════════════════════\n"
            "1. JAVOB BERISH USLUBI: Tinglovchilarning savollariga aniq, madaniyatli, samimiy va lo'nda (2-4 jumla) qilib javob bering. Instagram chatiga mos, o'qishga juda qulay bo'lsin.\n"
            "2. ANIQ NARXLAR VA MUDDATLAR:\n"
            "   - Gid-ekskursiyachi qayta tayyorlash: 4 oy, 5 500 000 so'm, rasmiy diplom + butun O'zbekiston bo'ylab professional beyjik.\n"
            "   - Gid-ekskursiyachilar malaka oshirish: 1 oy (72 soat), 2 350 000 so'm, rasmiy sertifikat.\n"
            "   - Turagentlik kursi: 1 oy, 2 350 000 so'm, rasmiy sertifikat.\n"
            "   - Turoperatorlik kursi: 1 oy, 2 350 000 so'm, rasmiy sertifikat.\n"
            "   - Agar tinglovchi 'Sertifikatim bor edi, muddati tugagan' desa — 1 oylik Malaka oshirish kursini (2 350 000 so'm) tavsiya qiling.\n"
            "   - Agar 'Noldan o'rganmoqchiman, yangi kasb olmoqchiman' desa — 4 oylik Gid qayta tayyorlash (diplom + beyjik) yoki Turagentlik / Turoperatorlik kursini tavsiya qiling.\n"
            "3. 🌐 HAVOLALARNING QAT'IY CHEGARASI (O'TA MUHIM):\n"
            "   - Agar tinglovchi Front Office, Housekeeping, masofaviy/onlayn o'qish yoki sayt haqida so'rasa: DARHOL https://tourism-edu.uz rasmiy ta'lim platformamiz havolasini bering.\n"
            "   - Hotel Operations 27-sahifalik PDF havolasi (Telegram: https://t.me/MyMarketingAndPrBot?start=hotel, to'g'ridan-to'g'ri: https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf) hamda Zoho ariza shakli (https://survey.zohopublic.com/zs/jQCZao) FAQAT VA FAQAT tinglovchi «Hotel Operations and Innovation» kursi haqida so'ragandagina beriladi!\n"
            "   - BOSHQA HECH QANDAY KURSGA (Gid-ekskursiyachi, Turagentlik, Turoperatorlik, Front Office, Housekeeping) BU PDF VA ZOHO ARIZA HAVOLALARINI ASLO QO'SHMANG! Har bir kursga o'zining aniq ma'lumoti beriladi.\n"
            "4. RO'YXATDAN O'TISH VA TELEFON RAQAM (LEAD GENERATION):\n"
            "   - Agar tinglovchi hali telefon raqamini bermagan bo'lsa: uning savoliga (narx, muddat, diplom, onlayn o'qish va h.k.) to'liq va aniq javob bering, so'ng javobingiz oxirida muloyimlik bilan kursga ro'yxatdan o'tish yoki batafsil ma'lumot yuborish uchun ism va telefon raqamini so'rang.\n"
            "   - Agar tinglovchi allaqachon telefon raqamini taqdim etgan bo'lsa: Undan HECH QACHON qayta raqam so'ramang! Savoliga to'g'ridan-to'g'ri, samimiy va to'liq javob bering.\n"
            "5. QAT'IY TIL QOIDASI: Tinglovchi qaysi tilda (o'zbek, rus yoki ingliz) yozsa, 100% FAQAT VA FAQAT O'SHA TILDA javob bering!\n"
            "   - Ruscha yozsa — to'liq rus tilida ('Курс переподготовки гидов: 4 месяца, диплом и бейдж гида по всему Узбекистану, стоимость 5 500 000 сум...', 'Повышение квалификации: 1 месяц (72 ч), 2 350 000 сум...', 'Турагентство / Туроператор: 1 месяц, сертификат, 2 350 000 сум...').\n"
            "   - O'zbekcha yozsa — to'liq o'zbek tilida.\n"
            "   - Inglizcha yozsa — to'liq ingliz tilida.\n"
            "6. SALOMLASHISH QOIDASI: Faqat birinchi xabarda salomlashing. Keyingi har bir xabarda qayta-qayta salomlashmang. Darhol to'g'ridan-to'g'ri savolga javob bering.\n"
            "7. Rasmiy veb-saytimiz yoki onlayn ta'lim platformamiz havolasi: https://tourism-edu.uz"
        )
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Eski havola va eski final_message larni yangilash (foydalanuvchi talabiga ko'ra)
    cursor.execute("UPDATE settings SET value = 'https://tourism-edu.uz' WHERE key = 'default_promo_link'")
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'final_message'", (default_settings["final_message"],))
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'ai_system_prompt'", (default_settings["ai_system_prompt"],))

    # Rasmiy video kampaniyalarini kiritish (Reels va Postlar)
    official_campaigns = [
        (
            1,
            "Hotel Operations and Innovation 2026–2027",
            "hotel operations, hotel operation, operations, innovation, inavation, un tourism, 27 bet, 27 sahifa",
            "18122374856317012",
            "https://www.instagram.com/reel/DerPZSNNS0F/",
            "Directingizga Hotel Operations dasturi va to'liq PDF rejani yubordik! 📩",
            "Assalomu alaykum! UN Tourism shafeligidagi \"Hotel Operations and Innovation 2026–2027\" xalqaro qayta tayyorlash dasturiga xush kelibsiz. 🏨✨\n\nTo'liq 27 sahifalik o'quv rejasini (PDF) Telegram orqali yuklab olishingiz mumkin:\n👉 https://t.me/MyMarketingAndPrBot?start=hotel\n\nYoki brauzerda yuklab oling:\n📥 https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n\nSavollaringiz bo'lsa, qaysi modul qiziqtirayotganini yozing yoki mutaxassisimiz bog'lanishi uchun ismingiz va raqamingizni qoldiring 😊",
            "https://survey.zohopublic.com/zs/jQCZao",
            1
        ),
        (
            2,
            "Hotel Operations and Innovation",
            "hotel operations, menejermisiz, mehmonxona rahbar, boshliq",
            "18398194846204313",
            "https://www.instagram.com/reel/DeZbpoZtFw0/",
            "Directingizga dastur va to'liq ma'lumotni yubordik! 📩",
            "Assalomu alaykum! Mehmonxona sohasi rahbarlari uchun mo'ljallangan «Hotel Operations and Innovation» xalqaro dasturimizga qiziqqaningiz uchun rahmat. 🏨\n\nDastur bo'yicha to'liq PDF reja va narxlarni taqdim etishimiz uchun ismingiz va telefon raqamingizni qoldiring 😊",
            "https://survey.zohopublic.com/zs/jQCZao",
            1
        ),
        (
            3,
            "Gid-ekskursiyachi (Qayta tayyorlash)",
            "gid, ekskursavod, ekskursiyachi, noldan, diplom, beyjik, +, narx, dastur",
            "18021025358899605",
            "https://www.instagram.com/reel/DbDpNKLKgll/",
            "Directingizga Gid-ekskursiyachi kursi dasturini yubordik! 📩",
            "Assalomu alaykum! 4 oylik «Professional Gid-ekskursiyachi» qayta tayyorlash kursimizga xush kelibsiz! 🌍\n\nKurs yakunida rasmiy davlat diplomi va butun O'zbekiston bo'ylab amal qiluvchi rasmiy beyjik beriladi. Narxi: 5 500 000 so'm.\n\nBatafsil ma'lumot olish yoki ro'yxatdan o'tish uchun ismingiz va telefon raqamingizni qoldiring 😊",
            "https://tourism-edu.uz",
            1
        ),
        (
            4,
            "Turagentlik kursi",
            "turagent, agent, agentlik, +, narx, dastur",
            "17891059488656047",
            "https://www.instagram.com/p/DcQTeaKTBOa/",
            "Directingizga Turagentlik kursi bo'yicha ma'lumot yubordik! 📩",
            "Assalomu alaykum! 1 oylik «Turagentlik» kursimizga qiziqqaningiz uchun rahmat! ✈️ Narxi: 2 350 000 so'm, rasmiy sertifikat beriladi.\n\nBatafsil ma'lumot olish uchun ismingiz va telefon raqamingizni qoldiring 😊",
            "https://tourism-edu.uz",
            1
        ),
        (
            5,
            "Turoperatorlik kursi",
            "turoperator, operator, turpaket, +, narx",
            "18339193003251888",
            "https://www.instagram.com/p/DbXj3F1joxH/",
            "Directingizga Turoperatorlik kursi dasturini yubordik! 📩",
            "Assalomu alaykum! 1 oylik «Turoperatorlik» kursimizga xush kelibsiz! 🌍 Narxi: 2 350 000 so'm, rasmiy sertifikat beriladi.\n\nBatafsil ma'lumot olish uchun ismingiz va telefon raqamingizni qoldiring 😊",
            "https://tourism-edu.uz",
            1
        ),
        (
            6,
            "Onlayn ta'lim platformasi",
            "front office, housekeeping, onlayn, online, masofaviy, platforma, tourism-edu",
            "18029301782836925",
            "https://www.instagram.com/reel/DbM6EinhiZI/",
            "Directingizga onlayn platforma havolasini yubordik! 📩",
            "Assalomu alaykum! Bizning rasmiy onlayn ta'lim platformamiz: https://tourism-edu.uz 💻\n\nPlatformada Front Office va Housekeeping onlayn kurslarida masofadan to'liq o'qib, rasmiy sertifikat olishingiz mumkin. Bog'lanishimiz uchun ismingiz va telefon raqamingizni qoldiring 😊",
            "https://tourism-edu.uz",
            1
        )
    ]
    for c_item in official_campaigns:
        cursor.execute("""
            INSERT OR REPLACE INTO campaigns (
                id, name, trigger_keyword, media_id, media_url, public_reply, dm_welcome, promo_link, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            c_item[0], c_item[1], c_item[2], c_item[3], c_item[4], c_item[5], c_item[6], c_item[7], c_item[8],
            datetime.now().isoformat()
        ))

    # Agar zaxiradagi sozlamalar mavjud bo'lsa tiklash
    if os.path.exists(SETTINGS_BACKUP_FILE):
        try:
            with open(SETTINGS_BACKUP_FILE, "r", encoding="utf-8") as f:
                backup_settings = json.load(f)
            for k, v in backup_settings.items():
                if v:
                    if k == "default_promo_link" and "tourism-academy.uz" in v:
                        v = "https://tourism-edu.uz"
                    if k == "ai_system_prompt":
                        v = default_settings["ai_system_prompt"]
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
        except Exception:
            pass

    # Eng so'nggi rasmiy AI tizim ko'rsatmasini (promt) kafolatlangan yangilash
    cursor.execute("UPDATE settings SET value = ? WHERE key = 'ai_system_prompt'", (default_settings["ai_system_prompt"],))
    cursor.execute("UPDATE settings SET value = 'https://tourism-edu.uz' WHERE key = 'default_promo_link'")

    # Gemini API kalit mavjudligini kafolatlash
    cursor.execute("SELECT value FROM settings WHERE key = 'gemini_api_key'")
    current_key_row = cursor.fetchone()
    if not current_key_row or not current_key_row[0] or not current_key_row[0].strip():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('gemini_api_key', ?)", (DEFAULT_GEMINI_KEY,))

    # Doimiy saqlanadigan lidlarni zaxiradan tiklash (agar mavjud bo'lsa)
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                backup_leads = json.load(f)
            for b in backup_leads:
                ig_id = b.get("instagram_id")
                if ig_id:
                    cursor.execute("SELECT id FROM clients WHERE instagram_id = ?", (ig_id,))
                    row = cursor.fetchone()
                    if not row:
                        if b.get("id"):
                            cursor.execute("""
                                INSERT OR REPLACE INTO clients (
                                    id, instagram_id, username, full_name, phone_number, source,
                                    campaign, step, last_message, lead_status, is_follower,
                                    ai_summary, manager_comment, chat_history,
                                    manager_name, manager_time, created_at, updated_at,
                                    followup_count, last_followup_at, tg_message_id, profile_pic
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                b.get("id"),
                                ig_id,
                                b.get("username", ""),
                                b.get("full_name"),
                                b.get("phone_number"),
                                b.get("source", "Direct"),
                                b.get("campaign", "Umumiy"),
                                b.get("step", "completed"),
                                b.get("last_message", ""),
                                b.get("lead_status", "yangi"),
                                b.get("is_follower", 0),
                                b.get("ai_summary", ""),
                                b.get("manager_comment", ""),
                                b.get("chat_history", "[]"),
                                b.get("manager_name", ""),
                                b.get("manager_time", ""),
                                b.get("created_at", datetime.now().isoformat()),
                                b.get("updated_at", datetime.now().isoformat()),
                                b.get("followup_count", 0),
                                b.get("last_followup_at", ""),
                                b.get("tg_message_id"),
                                b.get("profile_pic", "")
                            ))
                        else:
                            cursor.execute("""
                                INSERT INTO clients (
                                    instagram_id, username, full_name, phone_number, source,
                                    campaign, step, last_message, lead_status, is_follower,
                                    ai_summary, manager_comment, chat_history,
                                    manager_name, manager_time, created_at, updated_at,
                                    followup_count, last_followup_at, tg_message_id, profile_pic
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                ig_id,
                                b.get("username", ""),
                                b.get("full_name"),
                                b.get("phone_number"),
                                b.get("source", "Direct"),
                                b.get("campaign", "Umumiy"),
                                b.get("step", "completed"),
                                b.get("last_message", ""),
                                b.get("lead_status", "yangi"),
                                b.get("is_follower", 0),
                                b.get("ai_summary", ""),
                                b.get("manager_comment", ""),
                                b.get("chat_history", "[]"),
                                b.get("manager_name", ""),
                                b.get("manager_time", ""),
                                b.get("created_at", datetime.now().isoformat()),
                                b.get("updated_at", datetime.now().isoformat()),
                                b.get("followup_count", 0),
                                b.get("last_followup_at", ""),
                                b.get("tg_message_id"),
                                b.get("profile_pic", "")
                            ))
                    else:
                        cursor.execute("""
                            UPDATE clients SET 
                                phone_number = COALESCE(NULLIF(NULLIF(NULLIF(?, ''), '—'), 'None'), phone_number),
                                full_name = COALESCE(NULLIF(NULLIF(NULLIF(?, ''), 'Kiritilmagan'), 'None'), full_name),
                                campaign = CASE WHEN (? IS NOT NULL AND ? != '' AND ? != 'Umumiy') THEN ? WHEN (campaign = '' OR campaign IS NULL OR campaign = 'Umumiy') THEN COALESCE(?, campaign) ELSE campaign END,
                                source = CASE WHEN (? IS NOT NULL AND ? != '' AND ? != 'Direct') THEN ? WHEN (source = '' OR source IS NULL OR source = 'Direct') THEN COALESCE(?, source) ELSE source END,
                                lead_status = COALESCE(NULLIF(?, ''), lead_status),
                                manager_name = COALESCE(NULLIF(?, ''), manager_name),
                                manager_comment = COALESCE(NULLIF(?, ''), manager_comment),
                                manager_time = COALESCE(NULLIF(?, ''), manager_time),
                                ai_summary = COALESCE(NULLIF(?, ''), ai_summary),
                                chat_history = CASE WHEN (? IS NOT NULL AND ? != '' AND ? != '[]') THEN ? ELSE chat_history END,
                                step = CASE WHEN (step = '' OR step IS NULL OR step = 'new') AND ? != '' THEN 'completed' ELSE step END,
                                followup_count = COALESCE(?, followup_count),
                                last_followup_at = CASE WHEN (last_followup_at = '' OR last_followup_at IS NULL) THEN ? ELSE last_followup_at END,
                                tg_message_id = COALESCE(?, tg_message_id),
                                created_at = CASE WHEN (? IS NOT NULL AND ? != '' AND (created_at LIKE '2026-10-28T09:2%' OR created_at LIKE '2026-10-28T09:4%')) THEN ? ELSE created_at END,
                                updated_at = COALESCE(NULLIF(?, ''), updated_at)
                            WHERE instagram_id = ?
                        """, (
                            b.get("phone_number"),
                            b.get("full_name"),
                            b.get("campaign"), b.get("campaign"), b.get("campaign"), b.get("campaign"), b.get("campaign"),
                            b.get("source"), b.get("source"), b.get("source"), b.get("source"), b.get("source"),
                            b.get("lead_status", "") or "",
                            b.get("manager_name", "") or "",
                            b.get("manager_comment", "") or "",
                            b.get("manager_time", "") or "",
                            b.get("ai_summary", "") or "",
                            b.get("chat_history", "[]"), b.get("chat_history", "[]"), b.get("chat_history", "[]"), b.get("chat_history", "[]"),
                            b.get("phone_number", "") or "",
                            b.get("followup_count"),
                            b.get("last_followup_at", ""),
                            b.get("tg_message_id"),
                            b.get("created_at"), b.get("created_at"), b.get("created_at"),
                            b.get("updated_at", ""),
                            ig_id
                        ))
        except Exception:
            pass

    # Target davridan oldingi arxivlangan eski yozishmalarni tozalash (faqat target davridagi faol lidlar qoladi)
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                valid_ig_ids = [str(b.get("instagram_id")) for b in json.load(f) if b.get("instagram_id")]
            if valid_ig_ids:
                placeholders = ",".join(["?"] * len(valid_ig_ids))
                cursor.execute(f"DELETE FROM clients WHERE instagram_id NOT IN ({placeholders}) AND (manager_name IS NULL OR manager_name = '' OR manager_name = '—')", valid_ig_ids)
        except Exception:
            pass

    # Operatorlarni zaxiradan tiklash (agar mavjud bo'lsa)
    if os.path.exists(OPERATORS_BACKUP_FILE):
        try:
            cursor.execute("UPDATE operators SET username = 'jasurraxmanov' WHERE username = 'jasur'")
            cursor.execute("DELETE FROM operators WHERE username = 'operator'")
            cursor.execute("UPDATE operators SET allowed_directions = 'hotel' WHERE allowed_directions = 'hotel_operations'")
            cursor.execute("UPDATE operators SET role = 'supervisor', allowed_directions = 'all' WHERE username IN ('shirin', 'jasurraxmanov')")
            cursor.execute("UPDATE clients SET manager_name = 'Shirin Yakubovna' WHERE manager_name IN ('@shirin_yakubovna', '@shirin', 'shirin_yakubovna', 'shirin')")
            with open(OPERATORS_BACKUP_FILE, "r", encoding="utf-8") as f:
                backup_ops = json.load(f)
            for op in backup_ops:
                cursor.execute("SELECT id FROM operators WHERE username = ?", (op.get("username"),))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO operators (username, password_hash, display_name, phone, role, is_active, created_at, last_login, allowed_directions)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        op.get("username"),
                        op.get("password_hash"),
                        op.get("display_name", op.get("username")),
                        op.get("phone", ""),
                        op.get("role", "operator"),
                        op.get("is_active", 1),
                        op.get("created_at"),
                        op.get("last_login"),
                        op.get("allowed_directions", "all")
                    ))
                else:
                    cursor.execute("""
                        UPDATE operators SET
                            display_name = ?,
                            phone = COALESCE(NULLIF(?, ''), phone),
                            role = ?,
                            is_active = COALESCE(?, is_active),
                            allowed_directions = COALESCE(NULLIF(?, ''), allowed_directions, 'all'),
                            password_hash = COALESCE(NULLIF(?, ''), password_hash)
                        WHERE username = ?
                    """, (
                        op.get("display_name", op.get("username")),
                        op.get("phone", ""),
                        op.get("role", "operator"),
                        op.get("is_active", 1),
                        op.get("allowed_directions", "all"),
                        op.get("password_hash"),
                        op.get("username")
                    ))
        except Exception:
            pass

    # Faoliyat jurnalini zaxiradan tiklash (agar mavjud bo'lsa)
    if os.path.exists(ACTIVITY_LOGS_BACKUP_FILE):
        try:
            with open(ACTIVITY_LOGS_BACKUP_FILE, "r", encoding="utf-8") as f:
                backup_logs = json.load(f)
            for log in backup_logs:
                cursor.execute("SELECT id FROM activity_logs WHERE id = ?", (log.get("id"),))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO activity_logs (id, client_id, operator_name, action_type, details, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        log.get("id"),
                        log.get("client_id"),
                        log.get("operator_name"),
                        log.get("action_type"),
                        log.get("details"),
                        log.get("created_at")
                    ))
        except Exception:
            pass

    # Sozlamalar zaxirasini yangilab qo'yish
    try:
        cursor.execute("SELECT key, value FROM settings")
        all_s = {r[0]: r[1] for r in cursor.fetchall()}
        all_s.pop("gemini_api_key", None)
        with open(SETTINGS_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(all_s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    conn.commit()
    conn.close()


def sync_leads_backup():
    """Lidlarni doimiy JSON zaxira faylida saqlab borish"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        if rows:
            with open(BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def sync_settings_backup():
    """Barcha CRM sozlamalarini JSON faylga saqlab borish"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = {r["key"]: r["value"] for r in cursor.fetchall()}
        conn.close()
        if rows:
            safe_rows = dict(rows)
            safe_rows.pop("gemini_api_key", None)
            with open(SETTINGS_BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(safe_rows, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def sync_operators_backup():
    """Barcha operatorlarni JSON faylga saqlab borish"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM operators ORDER BY id ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        if rows:
            with open(OPERATORS_BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

AVAILABLE_DIRECTIONS = [
    {"key": "front_office", "name": "💻 Front Office (Onlayn)", "short": "Front Office"},
    {"key": "hotel", "name": "🏨 Hotel Operations", "short": "Hotel Operations"},
    {"key": "gid_qayta", "name": "🌏 Gidlik (Qayta tayyorlash)", "short": "Gidlik (Qayta)"},
    {"key": "gid_malaka", "name": "🗺️ Gidlik (Malaka oshirish)", "short": "Gidlik (Malaka)"},
    {"key": "turagent", "name": "✈️ Turagentlik", "short": "Turagentlik"},
    {"key": "turoperator", "name": "✈️ Turoperatorlik", "short": "Turoperatorlik"},
    {"key": "narx", "name": "💰 Kurslar narxi", "short": "Kurslar narxi"},
    {"key": "dastur", "name": "📄 O'quv dasturi", "short": "O'quv dasturi"},
    {"key": "konsultatsiya", "name": "💬 Batafsil konsultatsiya", "short": "Konsultatsiya"},
    {"key": "umumiy", "name": "💬 Boshqa / Umumiy", "short": "Boshqa"},
]

def get_lead_direction_key(campaign: str) -> str:
    """Mijoz kampaniyasi / so'roviga qarab yo'nalish kalitini aniqlash"""
    c = (campaign or "").lower().strip()
    if any(k in c for k in ["front", "housekeeping", "xona tozalash", "tourism-edu", "online", "onlayn"]):
        return "front_office"
    if any(k in c for k in ["hotel", "mehmonxona", "operations"]):
        return "hotel"
    if "malaka" in c:
        return "gid_malaka"
    if any(k in c for k in ["gid", "ekskurs"]):
        return "gid_qayta"
    if "turagent" in c:
        return "turagent"
    if "turoperator" in c:
        return "turoperator"
    if any(k in c for k in ["narx", "qancha", "narxi"]):
        return "narx"
    if any(k in c for k in ["dastur", "modul"]):
        return "dastur"
    if any(k in c for k in ["konsultatsiya", "batafsil"]):
        return "konsultatsiya"
    return "umumiy"

def get_all_operators() -> list:
    """Barcha operatorlar ro'yxatini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, display_name, phone, role, is_active, created_at, last_login, allowed_directions, password_hash FROM operators ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_operator_by_username(username: str) -> dict | None:
    """Username bo'yicha operatorni topish"""
    if not username:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM operators WHERE LOWER(username) = LOWER(?) OR (LOWER(?) = 'jasur' AND LOWER(username) = 'jasurraxmanov')",
        (username.strip(), username.strip())
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_operator_by_id(op_id: int) -> dict | None:
    """ID bo'yicha operatorni topish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operators WHERE id = ?", (op_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def find_matching_operator(manager_val: str) -> dict | None:
    """Operatorni username yoki display_name bo'yicha moslashtirib topish"""
    if not manager_val or str(manager_val).strip() in ["—", "none", "", "Biriktirilmagan (Yangi)", "⚪ Biriktirilmagan", "null", "None"]:
        return None
    m = str(manager_val).lower().replace("@", "").strip()
    ops = get_all_operators()
    for op in ops:
        op_u = (op.get("username") or "").lower().strip()
        op_d = (op.get("display_name") or "").lower().strip()
        if m == op_u or m == op_d:
            return op
        if op_u and (op_u in m or m in op_u):
            return op
        if op_d and (op_d in m or m in op_d or op_d.replace(" ", "_") in m or m.replace("_", " ") in op_d):
            return op
    return None

def create_operator(username: str, password: str, display_name: str, phone: str = "", role: str = "operator", allowed_directions: str = "all") -> int:
    """Yangi operator qo'shish"""
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_operator_password(password)
    now_iso = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO operators (username, password_hash, display_name, phone, role, is_active, created_at, allowed_directions)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
    """, (username.strip().lower(), pwd_hash, display_name.strip(), phone.strip(), role, now_iso, allowed_directions or "all"))
    conn.commit()
    op_id = cursor.lastrowid
    conn.close()
    sync_operators_backup()
    return op_id

def update_operator(op_id: int, **kwargs):
    """Operator ma'lumotlarini yoki parolini yangilash"""
    if not kwargs:
        return
    conn = get_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    for k, v in kwargs.items():
        if k == "password":
            fields.append("password_hash = ?")
            values.append(hash_operator_password(v))
        elif k in ["display_name", "phone", "role", "is_active", "last_login", "allowed_directions"]:
            fields.append(f"{k} = ?")
            values.append(v)
    if fields:
        values.append(op_id)
        cursor.execute(f"UPDATE operators SET {', '.join(fields)} WHERE id = ?", tuple(values))
        conn.commit()
    conn.close()
    sync_operators_backup()

def delete_operator(op_id: int):
    """Operatorni o'chirish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM operators WHERE id = ?", (op_id,))
    conn.commit()
    conn.close()
    sync_operators_backup()

# Modul yuklanganda bazani avtomatik tayyorlab qo'yish
init_db()
sync_leads_backup()
sync_settings_backup()
sync_operators_backup()

def get_or_create_client(instagram_id: str) -> dict:
    """Mijozni bazadan olish yoki yangi bo'lsa yaratish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE instagram_id = ?", (instagram_id,))
    row = cursor.fetchone()

    now = now_uzb_iso()
    if not row:
        cursor.execute(
            "INSERT INTO clients (instagram_id, step, created_at, updated_at) VALUES (?, 'start', ?, ?)",
            (instagram_id, now, now)
        )
        conn.commit()
        cursor.execute("SELECT * FROM clients WHERE instagram_id = ?", (instagram_id,))
        row = cursor.fetchone()
        sync_leads_backup()

    client_dict = dict(row)
    conn.close()
    return client_dict

def update_client(instagram_id: str, **kwargs):
    """Mijoz ma'lumotlarini (ism, telefon, bosqich) yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    kwargs["updated_at"] = now_uzb_iso()
    
    fields = [f"{k} = ?" for k in kwargs.keys()]
    values = list(kwargs.values())
    values.append(instagram_id)
    
    sql = f"UPDATE clients SET {', '.join(fields)} WHERE instagram_id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()
    sync_leads_backup()

def get_client_by_id(client_id: int) -> dict | None:
    """Mijozni ID raqami bo'yicha olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_client_by_id(client_id: int, **kwargs):
    """Mijozni ID raqami bo'yicha holati yoki mas'ul xodimini yangilash"""
    conn = get_connection()
    cursor = conn.cursor()
    kwargs["updated_at"] = now_uzb_iso()
    fields = [f"{k} = ?" for k in kwargs.keys()]
    values = list(kwargs.values())
    values.append(client_id)
    sql = f"UPDATE clients SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(sql, values)
    conn.commit()
    conn.close()
    sync_leads_backup()

def get_client_by_tg_message_id(message_id: int) -> dict | None:
    """Telegram xabar ID si bo'yicha lidni topish (Reply orqali izoh yozilganda)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE tg_message_id = ?", (message_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def append_client_chat_history(instagram_id: str, role: str, text: str, manager_name: str = ""):
    """Mijoz bilan Direct suhbat tarixini saqlab borish (AI tahlili va kontekst uchun)"""
    if not instagram_id or not text:
        return
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chat_history FROM clients WHERE instagram_id = ?", (instagram_id,))
        row = cursor.fetchone()
        history = []
        if row and row["chat_history"]:
            try:
                history = json.loads(row["chat_history"])
            except Exception:
                history = []
        
        now_dt = now_uzb()
        now_time = now_dt.strftime("%d.%m %H:%M")
        msg_obj = {"role": role, "text": text.strip(), "time": now_time, "date": now_dt.strftime("%d.%m.%Y")}
        if manager_name:
            msg_obj["manager"] = manager_name
        history.append(msg_obj)
        # Oxirgi 30 ta xabarni saqlash
        if len(history) > 30:
            history = history[-30:]
            
        cursor.execute("UPDATE clients SET chat_history = ?, updated_at = ? WHERE instagram_id = ?", (
            json.dumps(history, ensure_ascii=False),
            now_uzb_iso(),
            instagram_id
        ))
        conn.commit()
        conn.close()
        sync_leads_backup()
    except Exception as e:
        logger.error(f"Suhbat tarixini saqlashda xatolik: {e}")

def set_client_ai_paused(client_id: int, paused: bool) -> bool:
    """Mijoz uchun AI avtomatik javoblarini to'xtatish (1) yoki yoqish (0)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE clients SET ai_paused = ?, updated_at = ? WHERE id = ?", (
            1 if paused else 0,
            now_uzb_iso(),
            client_id
        ))
        conn.commit()
        conn.close()
        sync_leads_backup()
        return True
    except Exception as e:
        logger.error(f"set_client_ai_paused xatolik: {e}")
        return False

def get_client_chat_history(instagram_id: str) -> list:
    """Mijoz suhbat tarixini ro'yxat ko'rinishida olish"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chat_history FROM clients WHERE instagram_id = ?", (instagram_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row["chat_history"]:
            return json.loads(row["chat_history"])
    except Exception:
        pass
    return []

def update_client_manager_comment(client_id: int, comment: str, manager_name: str = "") -> dict | None:
    """Xodim yoki mutaxassis izohini CRM yoki Telegramdan saqlash"""
    conn = get_connection()
    cursor = conn.cursor()
    now_str = now_uzb_str()
    now_iso = now_uzb_iso()
    if manager_name:
        cursor.execute("""
            UPDATE clients SET 
                manager_comment = ?, 
                manager_name = ?, 
                manager_time = ?, 
                updated_at = ? 
            WHERE id = ?
        """, (comment.strip(), manager_name, now_str, now_iso, client_id))
    else:
        cursor.execute("""
            UPDATE clients SET 
                manager_comment = ?, 
                manager_time = ?, 
                updated_at = ? 
            WHERE id = ?
        """, (comment.strip(), now_str, now_iso, client_id))
    conn.commit()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    row = cursor.fetchone()
    conn.close()
    sync_leads_backup()
    return dict(row) if row else None

def get_all_clients():
    """Barcha yig'ilgan mijozlar ro'yxatini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_abandoned_clients(min_minutes: int = 30, max_hours: int = 12) -> list:
    """
    Telefon raqamini qoldirmagan, suhbat to'xtab qolgan va belgilangan vaqt o'tgan mijozlarni topish.
    (Meta Instagram 24 soatlik oynasi doirasida qayta eslatma yuborish uchun)
    Qat'iy xavfsizlik:
    - faqat 'yangi' holatidagi lidlar (bog'lanilgan, jarayonda yoki boshqa holatdagi lidlarga aslo xabar yuborilmasin)
    - inson / mutaxassis biriktirilmagan bo'lishi shart
    - AI to'xtatilmagan (ai_paused != 1) bo'lishi shart
    - oxirgi xabar foydalanuvchi tomonidan bo'lishi shart (bot ketma-ket qayta yozmasligi uchun)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM clients 
        WHERE (step != 'completed' OR phone_number IS NULL OR phone_number = '')
          AND instagram_id IS NOT NULL 
          AND instagram_id != ''
          AND (lead_status IS NULL OR lead_status = 'yangi')
          AND (ai_paused IS NULL OR ai_paused = 0)
          AND (manager_name IS NULL OR manager_name = '' OR manager_name = '—')
          AND (followup_count IS NULL OR followup_count = 0)
        ORDER BY updated_at ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    eligible = []
    now = datetime.now()
    for c in rows:
        # Oxirgi xabarni tekshirish (bot ketma-ket o'ziga o'zi yozmasligi uchun)
        ch_raw = c.get("chat_history") or "[]"
        try:
            ch = json.loads(ch_raw) if isinstance(ch_raw, str) else ch_raw
        except Exception:
            ch = []
        if ch and len(ch) > 0:
            last_msg = ch[-1]
            if last_msg.get("role") in ["assistant", "manager", "operator"]:
                continue

        up_str = c.get("updated_at")
        if not up_str:
            continue
        try:
            up_time = datetime.fromisoformat(up_str)
            diff_seconds = (now - up_time).total_seconds()
            diff_minutes = diff_seconds / 60
            diff_hours = diff_seconds / 3600
            if diff_minutes >= min_minutes and diff_hours <= max_hours:
                eligible.append(c)
        except Exception:
            continue
    return eligible

def mark_client_followup_sent(client_id: int):
    """Mijozga avtomatik eslatma (Follow-up) yuborilganligini belgilash"""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    cursor.execute("""
        UPDATE clients SET 
            followup_count = COALESCE(followup_count, 0) + 1,
            last_followup_at = ?,
            updated_at = ?
        WHERE id = ?
    """, (now_iso, now_iso, client_id))
    conn.commit()
    conn.close()
    sync_leads_backup()

def mark_client_unresponsive_notified(client_id: int, tg_mid: int = 999999):
    """Javobsiz qolgan lid guruhga yuborilganini belgilash (qayta-qayta takrorlanishining oldini olish uchun)"""
    conn = get_connection()
    cursor = conn.cursor()
    now_iso = datetime.now().isoformat()
    cursor.execute("""
        UPDATE clients SET 
            tg_message_id = COALESCE(?, 999999),
            updated_at = ?
        WHERE id = ?
    """, (tg_mid, now_iso, client_id))
    conn.commit()
    conn.close()
    sync_leads_backup()

def get_unresponsive_followup_clients(min_minutes_after_followup: int = 30, max_hours: int = 168) -> list:
    """
    Eslatma (Follow-up) yuborilgan, lekin shunda ham raqam qoldirmagan va Telegram guruhiga
    hali yuborilmagan mijozlarni olish (operatorlar Direct orqali yozishi uchun).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM clients 
        WHERE (phone_number IS NULL OR phone_number = '' OR LENGTH(phone_number) < 9)
          AND instagram_id IS NOT NULL 
          AND instagram_id != ''
          AND (followup_count IS NOT NULL AND followup_count >= 1)
          AND (last_followup_at IS NOT NULL AND last_followup_at != '')
          AND (tg_message_id IS NULL OR tg_message_id <= 0)
        ORDER BY last_followup_at ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    eligible = []
    now = datetime.now()
    for c in rows:
        phone = c.get("phone_number")
        digits = re.sub(r"\D", "", str(phone or ""))
        if len(digits) >= 9:
            continue

        fol_str = c.get("last_followup_at")
        if not fol_str:
            continue
        try:
            fol_time = datetime.fromisoformat(fol_str)
            diff_seconds = (now - fol_time).total_seconds()
            diff_minutes = diff_seconds / 60
            diff_hours = diff_seconds / 3600
            if diff_minutes >= min_minutes_after_followup and diff_hours <= max_hours:
                eligible.append(c)
        except Exception:
            continue
    return eligible

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
    sync_settings_backup()

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

def is_comment_processed(comment_id: str) -> bool:
    """Izohga avval javob berilganmi yoki yo'qligini tekshirish"""
    if not comment_id:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_comments WHERE comment_id = ?", (comment_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row)

def mark_comment_processed(comment_id: str):
    """Izohni qayta ishlangan deb belgilash"""
    if not comment_id:
        return
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO processed_comments (comment_id, created_at) VALUES (?, ?)",
            (comment_id, datetime.now().isoformat())
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def save_pending_comment(instagram_id: str, comment_id: str = "", media_id: str = "", source: str = "", campaign: str = "", comment_text: str = "", dm_welcome_text: str = "", username: str = ""):
    """Faqat izoh qoldirgan, lekin hali Directda javob yozmagan foydalanuvchini vaqtincha saqlash"""
    if not instagram_id:
        return
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO pending_comments 
            (instagram_id, comment_id, media_id, source, campaign, comment_text, dm_welcome_text, username, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (instagram_id, comment_id, media_id, source, campaign, comment_text, dm_welcome_text, username, now))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def get_pending_comment(instagram_id: str) -> dict | None:
    """Foydalanuvchining kutilayotgan izoh ma'lumotlarini olish"""
    if not instagram_id:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pending_comments WHERE instagram_id = ?", (instagram_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_pending_comment(instagram_id: str):
    """Directda javob bergach, kutilayotgan izohlar ro'yxatidan o'chirish"""
    if not instagram_id:
        return
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM pending_comments WHERE instagram_id = ?", (instagram_id,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def get_client_by_instagram_id(instagram_id: str) -> dict | None:
    """Mijozni faqat mavjud bo'lsa olish (yangi yaratmasdan)"""
    if not instagram_id:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE instagram_id = ?", (instagram_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_client_by_id(client_id: int):
    """Bitta lidni o'chirish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()
    sync_leads_backup()

def clear_all_clients():
    """Barcha test ma'lumotlarini tozalash"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clients")
    conn.commit()
    conn.close()
    sync_leads_backup()

def sync_activity_logs_backup():
    """Faoliyat jurnalini JSON zaxira faylida saqlash"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 500")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        if rows:
            with open(ACTIVITY_LOGS_BACKUP_FILE, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def log_activity(client_id: int, operator_name: str, action_type: str, details: str):
    """Mutaxassis yoki tizim harakatini audit jurnaliga yozish (Anti-Fraud monitoring uchun)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_logs (client_id, operator_name, action_type, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (client_id, (operator_name or "Tizim").strip(), action_type.strip(), details.strip(), now_uzb_iso()))
        conn.commit()
        conn.close()
        sync_activity_logs_backup()
    except Exception as e:
        logger.error(f"log_activity xatoligi: {e}")

def get_client_activity_logs(client_id: int) -> list:
    """Bitta lid bo'yicha barcha harakatlar tarixi"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM activity_logs WHERE client_id = ? ORDER BY id DESC", (client_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []

def get_recent_activity_logs(limit: int = 50) -> list:
    """Oxirgi mutaxassislar harakatlari (Audit & Nazorat uchun)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*, c.full_name as client_name, c.username as client_username, c.campaign as client_campaign
            FROM activity_logs a
            LEFT JOIN clients c ON a.client_id = c.id
            ORDER BY a.id DESC LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []





