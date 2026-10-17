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
            step TEXT DEFAULT 'new',
            last_message TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    # Agar jadval oldin yaratilgan bo'lsa, source ustunini qo'shib qo'yish
    try:
        cursor.execute("ALTER TABLE clients ADD COLUMN source TEXT DEFAULT 'Direct'")
    except sqlite3.OperationalError:
        pass  # Ustun allaqachon mavjud bo'lsa xatolik bermaydi
    conn.commit()
    conn.close()

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
