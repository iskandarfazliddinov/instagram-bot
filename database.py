import os
import re
import json
import sqlite3
from datetime import datetime

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
            last_login TIMESTAMP
        )
    """)

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

    # Standart matnlarni tekshirib kiritish
    default_settings = {
        "direct_welcome": "Assalomu alaykum! Xalqaro turizm akademiyasining Samarqand kampusi rasmiy sahifasiga xush kelibsiz. 😊\n\nSizni qiziqtirgan qayta tayyorlash va malaka oshirish kurslari bo'yicha ma'lumot olish uchun, iltimos, ismingizni qoldiring:",
        "ask_phone": "Rahmat, {name}! 🙌\n\nBatafsil o'quv dasturi, qabul shartlari va dars jadvalini yuborishimiz uchun telefon raqamingizni qoldiring (masalan: +998901234567):",
        "final_message": "Rahmat, tez orada siz bilan bog'lanamiz! 😊\n\nQuyidagi havola orqali akademiyamiz platformasidagi ta'lim yo'nalishlari bilan batafsil tanishishingiz mumkin:",
        "default_promo_link": "https://tourism-edu.uz",
        "admin_username": "admin",
        "admin_password": "admin",
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
            "- Telefon: +998 (90) 103 30 00\n"
            "- Email: info@tourism-edu.uz\n"
            "- Rasmiy veb-sayt va onlayn ta'lim platformasi: https://tourism-edu.uz\n\n"
            "══════════════════════════════════════════════════════════════\n"
            "🎓 QABUL BOSHLANGAN RASMIY KURSLAR VA TO'LIQ MA'LUMOTLAR:\n"
            "══════════════════════════════════════════════════════════════\n\n"
            "1. 🌍 GID-EKSKURSIYACHI QAYTA TAYYORLASH KURSI\n"
            "• Maqsad va kimlar uchun: Turizm sohasida yangi kasb egallashni, professional gid-ekskursiyachi bo'lishni va O'zbekistonning eng mashhur turistik shaharlarida faoliyat yuritishni xohlovchilar uchun (noldan yangi kasb egallovchilar).\n"
            "• Kurs davomiyligi: 4 oy.\n"
            "• O'quv dasturi: Gid-ekskursiyachi sifatida ishlash uchun zarur bo'lgan nazariy bilim va amaliy ko'nikmalar, mashhur turistik obidalar bo'yicha amaliyot.\n"
            "• Beriladigan rasmiy hujjatlar:\n"
            "  - Muvaffaqiyatli tamomlagandan so'ng rasmiy Qayta tayyorlash diplomi beriladi.\n"
            "  - Professional beyjik taqdim etiladi. Ushbu beyjik orqali butun O'zbekiston bo'ylab (Toshkent, Samarqand, Buxoro, Xiva, Shahrisabz va boshqalar) qonuniy va erkin gid sifatida faoliyat yuritish imkoniyati beriladi.\n"
            "• Karyera imkoniyatlari: Professional gid-ekskursiyachi sifatida ishlash, mahalliy va xorijiy sayyohlarga ekskursiyalar o'tkazish, turizmda o'z karyerasini boshlash, daromadni oshirish.\n"
            "• O'qish narxi: 5 500 000 so'm.\n\n"
            "2. 🗺 GID-EKSKURSIYACHILAR UCHUN MALAKA OSHIRISH KURSI\n"
            "• Maqsad va kimlar uchun: Amaldagi gid-ekskursiyachilar; sertifikatining amal qilish muddati tugagan gidlar; kasbiy bilim va amaliy ko'nikmalarini yangilashni istagan soha mutaxassislari.\n"
            "• Kurs davomiyligi: 1 oy (72 soat).\n"
            "• O'quv dasturi: Turizm sohasidagi bilimlarni yangilash, gidlik bo'yicha kasbiy malakani oshirish, ekskursiyalarni tashkil etish va o'tkazish bo'yicha bilimlarni mustahkamlash, kasbiy mahoratni rivojlantirish.\n"
            "• Beriladigan rasmiy hujjat: Kursni muvaffaqiyatli tamomlagach, belgilangan tartibda tegishli rasmiy davlat hujjati / malaka oshirish sertifikati taqdim etiladi.\n"
            "• O'qish narxi: 2 350 000 so'm.\n\n"
            "3. ✈️ TURAGENTLIK KURSI\n"
            "• Maqsad va kimlar uchun: Yangi kasb egallash va turizm sohasida o'z faoliyatini boshlashni xohlovchilar uchun.\n"
            "• Kurs davomiyligi: 1 oy.\n"
            "• O'quv dasturi: Turagentlik sohasida ishlash uchun zarur bo'lgan bilim va amaliy ko'nikmalar.\n"
            "• Beriladigan rasmiy hujjat: Kurs yakunida rasmiy sertifikat beriladi.\n"
            "• Karyera imkoniyatlari: Turagentlik kompaniyalarida ishlash, turizmda professional karyera boshlash, kelajakda o'z shaxsiy turagentligini ochish.\n"
            "• O'qish narxi: 2 350 000 so'm.\n\n"
            "4. ✈️ TUROPERATORLIK KURSI\n"
            "• Maqsad va kimlar uchun: Yangi kasb egallash va turizm sohasida turoperator sifatida faoliyat boshlashni xohlovchilar uchun.\n"
            "• Kurs davomiyligi: 1 oy.\n"
            "• O'quv dasturi: Turoperatorlik sohasida ishlash uchun zarur bilim va amaliy ko'nikmalar, turistik yo'nalishlar va sayohat paketlarini shakllantirish, logistika.\n"
            "• Beriladigan rasmiy hujjat: Kurs yakunida rasmiy sertifikat beriladi.\n"
            "• Karyera imkoniyatlari: Turoperator kompaniyalarida ishlash, turizmda karyera boshlash, sayohat paketlarini shakllantirish, kelajakda o'z turoperatorlik faoliyatini yo'lga qo'yish.\n"
            "• O'qish narxi: 2 350 000 so'm.\n\n"
            "5. 💻 ONLAYN TA'LIM PLATFORMASI (MASOFAVIY TA'LIM):\n"
            "• Rasmiy platforma va veb-sayt: https://tourism-edu.uz\n"
            "• Hozirda platformada mavjud rasmiy onlayn kurslar:\n"
            "  - 🏨 Front Office (Mehmonxona boshqaruvi va qabul bo'limi)\n"
            "  - 🧹 Housekeeping (Mehmonxona xo'jaligi va xizmat ko'rsatish)\n"
            "• Qulayliklari: Tinglovchilar istalgan joydan turib, platforma orqali masofadan to'liq o'qishlari mumkin.\n"
            "• Beriladigan hujjat: Platformada o'qib tamomlagandan so'ng rasmiy sertifikat beriladi!\n\n"
            "Boshqa qo'shimcha yo'nalishlar:\n"
            "- Mehmonxona xo'jaligi va boshqaruvi (Hotel Management)\n"
            "- Restoran ishi, servis va mehmondo'stlik (F&B Service)\n"
            "- Turizm menejmenti va zamonaviy raqamli marketing\n\n"
            "══════════════════════════════════════════════════════════════\n"
            "🎯 SIZNING ASOSIY MULOQOT VA JAVOB BERISH QOIDALARINGIZ:\n"
            "══════════════════════════════════════════════════════════════\n"
            "1. JAVOB BERISH USLUBI: Tinglovchilarning savollariga aniq, madaniyatli, samimiy va lo'nda (2-3 jumla) qilib javob bering. Instagram chatiga mos, o'qishga juda qulay bo'lsin.\n"
            "2. NARXLAR VA MA'LUMOTLAR BO'YICHA:\n"
            "   - Agar tinglovchi biron kurs narxini so'rasa, kursning aniq narxini (Gid qayta tayyorlash — 5 500 000 so'm, Gid malaka oshirish — 2 350 000 so'm, Turagentlik — 2 350 000 so'm, Turoperatorlik — 2 350 000 so'm) ochiq va aniq ayting.\n"
            "   - Muddati (4 oy yoki 1 oy) va beriladigan hujjatlarni (diplom, professional beyjik, sertifikat) aniq tushuntiring.\n"
            "   - Agar foydalanuvchi 'Menda sertifikat bor edi, muddati tugagan' desa — 1 oylik Malaka oshirish kursini (2 350 000 so'm) tavsiya qiling.\n"
            "   - Agar 'Noldan o'rganmoqchiman, yangi kasb olmoqchiman' desa — 4 oylik Gid qayta tayyorlash (5 500 000 so'm, diplom + beyjik) yoki Turagentlik / Turoperatorlik kursini tavsiya qiling.\n"
            "3. 🌐 ONLAYN O'QISH, SAYT VA PLATFORMA QOIDASI (O'TA MUHIM):\n"
            "   - Agar tinglovchi 'onlayn o'qimoqchiman', 'masofaviy o'qisa bo'ladimi', 'online platforma bormi', 'sayt bormi', 'saytini yubor' deb so'rasa:\n"
            "     Hech qachon havolasiz umumiy gaplar bilan cheklanmang! DARHOL birinchi javobning o'zidayoq quyidagilarni aniq ayting:\n"
            "     1) Rasmiy onlayn ta'lim platformamiz havolasini bering: https://tourism-edu.uz\n"
            "     2) Hozirda ushbu platformada aynan Front Office va Housekeeping yo'nalishlari bo'yicha onlayn darslar mavjudligini ayting.\n"
            "     3) Platformada to'liq onlayn o'qib, kurs yakunida rasmiy sertifikat olish mumkinligini tushuntiring.\n"
            "     4) Platformadan ro'yxatdan o'tishda yordam berish va to'liq ma'lumot yuborish uchun ism va telefon raqamini so'rang (agar hali bermagan bo'lsa).\n"
            "   - O'zbek tilidagi javob namunasi:\n"
            "     'Ha, albatta! Bizning https://tourism-edu.uz onlayn platformamizda hozirda Front Office va Housekeeping yo'nalishlari bo'yicha onlayn darslar mavjud. Platformada masofadan to'liq o'qib, rasmiy sertifikat olishingiz mumkin. Ro'yxatdan o'tishda yordam berishimiz uchun, iltimos, ismingiz va telefon raqamingizni qoldiring 😊'\n"
            "   - Rus tilidagi javob namunasi:\n"
            "     'Да, конечно! На нашей официальной платформе https://tourism-edu.uz сейчас доступны онлайн-курсы по направлениям Front Office и Housekeeping. Вы можете пройти обучение дистанционно и получить официальный сертификат. Чтобы мы помогли вам зарегистрироваться на платформе, пожалуйста, оставьте ваше имя и номер телефона 😊'\n"
            "4. RO'YXATDAN O'TISH VA TELEFON RAQAM (LEAD GENERATION):\n"
            "   - Agar tinglovchi hali telefon raqamini bermagan bo'lsa: uning savoliga (narx, muddat, diplom, onlayn o'qish va h.k.) to'liq va aniq javob bering, so'ng javobingiz oxirida muloyimlik bilan kursga ro'yxatdan o'tish yoki batafsil ma'lumot yuborish uchun ism va telefon raqamini so'rang.\n"
            "   - Agar tinglovchi allaqachon telefon raqamini taqdim etgan bo'lsa: Undan HECH QACHON qayta raqam so'ramang! Savoliga to'g'ridan-to'g'ri, samimiy va to'liq javob bering.\n"
            "5. QAT'IY TIL QOIDASI: Tinglovchi qaysi tilda (o'zbek, rus yoki ingliz) yozsa, 100% FAQAT VA FAQAT O'SHA TILDA javob bering!\n"
            "   - Ruscha yozsa — to'liq rus tilida ('Курс переподготовки гидов: 4 месяца, диплом и бейдж гида по всему Узбекистану, стоимость 5 500 000 сум...', 'Повышение квалификации: 1 месяц (72 ч), 2 350 000 сум...', 'Турагентство / Туроператор: 1 месяц, сертификат, 2 350 000 сум...').\n"
            "   - O'zbekcha yozsa — to'liq o'zbek tilida.\n"
            "   - Inglizcha yozsa — to'liq ingliz tilida.\n"
            "6. 🏨 «HOTEL OPERATIONS AND INNOVATION 2026–2027» DASTURI:\n"
            "• Tashkilotchi: UN Tourism va Xalqaro Turizm Akademiyasi Samarqand kampusi.\n"
            "• Kimlar uchun: Mehmonxona sohasi rahbarlari (menejerlar, bo'lim boshliqlari, supervayzerlar).\n"
            "• Dastur: 7 ta moduldan iborat nufuzli xalqaro qayta tayyorlash dasturi (Banqueting, Front Office, Housekeeping, F&B, Maintenance, Safety & Crisis, Revenue Management).\n"
            "• Muddat: 26-sentyabr — 1-noyabr 2026 gacha ro'yxatga olinadi. 30 nafar tinglovchi uchun joy cheklangan.\n"
            "• Onlayn ariza: https://survey.zohopublic.com/zs/jQCZao\n"
            "• Dasturni PDF formatda Telegramda yuklab olish: https://t.me/MyMarketingAndPrBot?start=hotel\n"
            "• Dasturni to'g'ridan-to'g'ri PDF yuklab olish: https://instagram-bot-zohg.onrender.com/static/hotel_operations.pdf\n"
            "• QOIDA: Agar tinglovchi Hotel Operations, mehmonxona kursi, dastur yoki PDF haqida so'rasa, 7 ta modul va xalqaro UN Tourism sertifikati haqida ma'lumot berib, PDF dasturni olish uchun Telegram havolamizni (https://t.me/MyMarketingAndPrBot?start=hotel) hamda ariza formasini (https://survey.zohopublic.com/zs/jQCZao) bering!\n\n"
            "7. SALOMLASHISH QOIDASI: Faqat birinchi xabarda salomlashing. Keyingi har bir xabarda qayta-qayta salomlashmang. Darhol to'g'ridan-to'g'ri savolga javob bering.\n"
            "8. Rasmiy veb-saytimiz yoki onlayn ta'lim platformamiz havolasi: https://tourism-edu.uz"
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
            "hotel, operations, inavation, innovation, mehmonxona, dastur, pdf, narx, reja",
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
            "hotel, operations, menejer, menejermisiz, boshliq, mehmonxona, +, narx, dastur",
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
            "front office, housekeeping, onlayn, online, masofaviy, platforma, +, narx",
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
                        if "tourism-academy.uz" in v:
                            v = v.replace("https://tourism-academy.uz", "https://tourism-edu.uz").replace("info@tourism-academy.uz", "info@tourism-edu.uz")
                        if "5 500 000" not in v or "QAYTA TAYYORLASH" not in v or "ONLAYN TA'LIM PLATFORMASI" not in v or "HOTEL OPERATIONS" not in v:
                            v = default_settings["ai_system_prompt"]
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
        except Exception:
            pass

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
                                phone_number = CASE WHEN (phone_number = '' OR phone_number IS NULL) THEN COALESCE(?, phone_number) ELSE phone_number END,
                                full_name = CASE WHEN (full_name = '' OR full_name IS NULL OR full_name = 'Noma\'lum') THEN COALESCE(?, full_name) ELSE full_name END,
                                campaign = CASE WHEN (? IS NOT NULL AND ? != '' AND ? != 'Umumiy') THEN ? WHEN (campaign = '' OR campaign IS NULL OR campaign = 'Umumiy') THEN COALESCE(?, campaign) ELSE campaign END,
                                source = CASE WHEN (? IS NOT NULL AND ? != '' AND ? != 'Direct') THEN ? WHEN (source = '' OR source IS NULL OR source = 'Direct') THEN COALESCE(?, source) ELSE source END,
                                lead_status = CASE WHEN (lead_status = '' OR lead_status IS NULL OR lead_status = 'boshlangich') AND ? != '' THEN ? ELSE lead_status END,
                                step = CASE WHEN (step = '' OR step IS NULL OR step = 'new') AND ? != '' THEN 'completed' ELSE step END,
                                followup_count = COALESCE(?, followup_count),
                                last_followup_at = CASE WHEN (last_followup_at = '' OR last_followup_at IS NULL) THEN ? ELSE last_followup_at END,
                                tg_message_id = COALESCE(?, tg_message_id)
                            WHERE instagram_id = ?
                        """, (
                            b.get("phone_number"),
                            b.get("full_name"),
                            b.get("campaign"), b.get("campaign"), b.get("campaign"), b.get("campaign"), b.get("campaign"),
                            b.get("source"), b.get("source"), b.get("source"), b.get("source"), b.get("source"),
                            b.get("phone_number", "") or "", b.get("lead_status", "yangi"),
                            b.get("phone_number", "") or "",
                            b.get("followup_count"),
                            b.get("last_followup_at", ""),
                            b.get("tg_message_id"),
                            ig_id
                        ))
        except Exception:
            pass

    # Operatorlarni zaxiradan tiklash (agar mavjud bo'lsa)
    if os.path.exists(OPERATORS_BACKUP_FILE):
        try:
            with open(OPERATORS_BACKUP_FILE, "r", encoding="utf-8") as f:
                backup_ops = json.load(f)
            for op in backup_ops:
                cursor.execute("SELECT id FROM operators WHERE username = ?", (op.get("username"),))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO operators (username, password_hash, display_name, phone, role, is_active, created_at, last_login)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        op.get("username"),
                        op.get("password_hash"),
                        op.get("display_name", op.get("username")),
                        op.get("phone", ""),
                        op.get("role", "operator"),
                        op.get("is_active", 1),
                        op.get("created_at"),
                        op.get("last_login")
                    ))
                else:
                    cursor.execute("""
                        UPDATE operators SET
                            password_hash = ?,
                            display_name = ?,
                            phone = COALESCE(NULLIF(?, ''), phone),
                            role = ?,
                            is_active = COALESCE(?, is_active)
                        WHERE username = ?
                    """, (
                        op.get("password_hash"),
                        op.get("display_name", op.get("username")),
                        op.get("phone", ""),
                        op.get("role", "operator"),
                        op.get("is_active", 1),
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

    # Standart operator mavjudligini ta'minlash
    cursor.execute("SELECT COUNT(*) FROM operators")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO operators (username, password_hash, display_name, phone, role, is_active, created_at)
            VALUES (?, ?, ?, '', 'operator', 1, ?)
        """, ("operator", hash_operator_password("operator123"), "Operator 1", datetime.now().isoformat()))

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

def get_all_operators() -> list:
    """Barcha operatorlar ro'yxatini olish"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, display_name, phone, role, is_active, created_at, last_login FROM operators ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def get_operator_by_username(username: str) -> dict | None:
    """Username bo'yicha operatorni topish"""
    if not username:
        return None
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operators WHERE LOWER(username) = LOWER(?)", (username.strip(),))
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

def create_operator(username: str, password: str, display_name: str, phone: str = "", role: str = "operator") -> int:
    """Yangi operator qo'shish"""
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_operator_password(password)
    now_iso = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO operators (username, password_hash, display_name, phone, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
    """, (username.strip().lower(), pwd_hash, display_name.strip(), phone.strip(), role, now_iso))
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
        elif k in ["display_name", "phone", "role", "is_active", "last_login"]:
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
    kwargs["updated_at"] = datetime.now().isoformat()
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
        
        now_time = datetime.now().strftime("%H:%M")
        msg_obj = {"role": role, "text": text.strip(), "time": now_time}
        if manager_name:
            msg_obj["manager"] = manager_name
        history.append(msg_obj)
        # Oxirgi 30 ta xabarni saqlash
        if len(history) > 30:
            history = history[-30:]
            
        cursor.execute("UPDATE clients SET chat_history = ?, updated_at = ? WHERE instagram_id = ?", (
            json.dumps(history, ensure_ascii=False),
            datetime.now().isoformat(),
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
            datetime.now().isoformat(),
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
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    now_iso = datetime.now().isoformat()
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
        """, (client_id, (operator_name or "Tizim").strip(), action_type.strip(), details.strip(), datetime.now().isoformat()))
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





