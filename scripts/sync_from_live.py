#!/usr/bin/env python3
"""
scripts/sync_from_live.py
Jonli serverdagi (Render) barcha lidlar, holatlar, biriktirilgan mas'ullar va
operatorlar ma'lumotlarini mahalliy zaxira fayllariga (leads_backup.json va operators_backup.json)
sinxronlashtirish skripti. Har bir deploydan oldin avtomatik ishlatiladi.
"""

import os
import sys
import json
import sqlite3
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LEADS_BACKUP = os.path.join(DATA_DIR, "leads_backup.json")
OPS_BACKUP = os.path.join(DATA_DIR, "operators_backup.json")
DB_PATH = os.path.join(DATA_DIR, "clients.db")

LIVE_URL = "https://instagram-bot-zohg.onrender.com"

def sync_live():
    print("🔄 Jonli serverdan ma'lumotlar tortib olinmoqda...")
    
    # 1. Mijozlar / Lidlar sinxroni
    try:
        req = urllib.request.urlopen(f"{LIVE_URL}/api/clients", timeout=30)
        data = json.loads(req.read().decode("utf-8"))
        live_clients = data.get("clients", [])
        if live_clients:
            # Mavjud zaxiradagi haqiqiy inson ismlarini va to'g'ri sanalarni saqlab qolish
            existing_names = {}
            existing_created_at = {}
            if os.path.exists(LEADS_BACKUP):
                try:
                    with open(LEADS_BACKUP, "r", encoding="utf-8") as f:
                        old_leads = json.load(f)
                        for l in old_leads:
                            u = l.get("username")
                            fn = l.get("full_name")
                            ca = l.get("created_at")
                            if u and fn and fn != u and fn not in ["None", "Kiritilmagan", "Noma'lum"]:
                                existing_names[u] = fn
                            if u and ca and not (ca.startswith("2026-10-28T09:2") or ca.startswith("2026-10-28T09:4")):
                                existing_created_at[u] = ca
                except Exception:
                    pass

            for cl in live_clients:
                u = cl.get("username")
                fn = cl.get("full_name")
                if u and u in existing_names and (not fn or fn == u or fn in ["None", "Kiritilmagan", "Noma'lum"]):
                    cl["full_name"] = existing_names[u]
                if u and u in existing_created_at:
                    cl_ca = cl.get("created_at", "")
                    if cl_ca.startswith("2026-10-28T09:2") or cl_ca.startswith("2026-10-28T09:4"):
                        cl["created_at"] = existing_created_at[u]

            with open(LEADS_BACKUP, "w", encoding="utf-8") as f:
                json.dump(live_clients, f, ensure_ascii=False, indent=2)
            print(f"✅ {len(live_clients)} ta lid zaxiraga (leads_backup.json) saqlandi.")

            # Mahalliy SQLite bazasini ham yangilash
            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                for cl in live_clients:
                    ig_id = cl.get("instagram_id")
                    c.execute("SELECT id FROM clients WHERE instagram_id = ?", (ig_id,))
                    row = c.fetchone()
                    if row:
                        c.execute("""
                            UPDATE clients SET
                                full_name = ?,
                                phone_number = ?,
                                lead_status = ?,
                                manager_name = ?,
                                manager_time = ?,
                                manager_comment = ?,
                                ai_summary = ?,
                                updated_at = ?
                            WHERE instagram_id = ?
                        """, (
                            cl.get("full_name"), cl.get("phone_number"), cl.get("lead_status"),
                            cl.get("manager_name"), cl.get("manager_time"), cl.get("manager_comment"),
                            cl.get("ai_summary"), cl.get("updated_at"), ig_id
                        ))
                    else:
                        c.execute("""
                            INSERT INTO clients (
                                instagram_id, full_name, phone_number, source, campaign, step, last_message,
                                created_at, updated_at, lead_status, manager_name, manager_time, tg_message_id,
                                username, profile_pic, is_follower, ai_summary, manager_comment, chat_history,
                                followup_count, last_followup_at, ai_paused
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            ig_id, cl.get("full_name", ""), cl.get("phone_number", ""), cl.get("source", ""),
                            cl.get("campaign", ""), cl.get("step", "completed"), cl.get("last_message", ""),
                            cl.get("created_at"), cl.get("updated_at"), cl.get("lead_status", "yangi"),
                            cl.get("manager_name"), cl.get("manager_time"), cl.get("tg_message_id", 0),
                            cl.get("username", ""), cl.get("profile_pic", ""), cl.get("is_follower", 0),
                            cl.get("ai_summary", ""), cl.get("manager_comment", ""), cl.get("chat_history", "[]"),
                            cl.get("followup_count", 0), cl.get("last_followup_at", ""), cl.get("ai_paused", 0)
                        ))
                conn.commit()
                conn.close()
                print("✅ Mahalliy SQLite bazasi jonli lidlar bilan sinxronlandi.")
    except Exception as e:
        print(f"⚠️ Lidlar sinxronida xatolik: {e}")

    # 2. Mutaxassislar (Operators) sinxroni
    try:
        req = urllib.request.urlopen(f"{LIVE_URL}/api/operators", timeout=20)
        data = json.loads(req.read().decode("utf-8"))
        live_ops = data.get("operators", [])
        if live_ops:
            # Mavjud parollar heshini saqlab qolish
            existing_hashes = {}
            if os.path.exists(OPS_BACKUP):
                with open(OPS_BACKUP, "r", encoding="utf-8") as f:
                    old_ops = json.load(f)
                    for o in old_ops:
                        existing_hashes[o.get("username")] = o.get("password_hash")

            merged_ops = []
            for o in live_ops:
                u = o.get("username")
                if u == "operator":
                    continue  # Eski default operatorni chetlab o'tish
                if not o.get("password_hash"):
                    o["password_hash"] = existing_hashes.get(u, "")
                merged_ops.append(o)

            with open(OPS_BACKUP, "w", encoding="utf-8") as f:
                json.dump(merged_ops, f, ensure_ascii=False, indent=2)
            print(f"✅ {len(merged_ops)} ta mutaxassis zaxiraga (operators_backup.json) saqlandi.")

            # Mahalliy SQLite bazasini ham yangilash
            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                for op in merged_ops:
                    u = op.get("username")
                    c.execute("SELECT id FROM operators WHERE username = ?", (u,))
                    row = c.fetchone()
                    if row:
                        c.execute("""
                            UPDATE operators SET
                                display_name = ?,
                                phone = ?,
                                role = ?,
                                is_active = ?,
                                allowed_directions = ?,
                                password_hash = COALESCE(NULLIF(?, ''), password_hash)
                            WHERE username = ?
                        """, (
                            op.get("display_name"), op.get("phone", ""), op.get("role", "operator"),
                            op.get("is_active", 1), op.get("allowed_directions", "all"),
                            op.get("password_hash", ""), u
                        ))
                    else:
                        c.execute("""
                            INSERT INTO operators (username, password_hash, display_name, phone, role, is_active, created_at, allowed_directions)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            u, op.get("password_hash", ""), op.get("display_name", u),
                            op.get("phone", ""), op.get("role", "operator"), op.get("is_active", 1),
                            op.get("created_at"), op.get("allowed_directions", "all")
                        ))
                conn.commit()
                conn.close()
    except Exception as e:
        print(f"⚠️ Mutaxassislar sinxronida xatolik: {e}")

    # 3. Sozlamalar (Settings) sinxroni
    SETTINGS_BACKUP = os.path.join(DATA_DIR, "settings_backup.json")
    try:
        req = urllib.request.urlopen(f"{LIVE_URL}/api/settings", timeout=20)
        data = json.loads(req.read().decode("utf-8"))
        live_settings = data.get("settings", {})
        if live_settings:
            with open(SETTINGS_BACKUP, "w", encoding="utf-8") as f:
                json.dump(live_settings, f, ensure_ascii=False, indent=2)
            print("✅ CRM sozlamalari zaxiraga (settings_backup.json) saqlandi.")

            if os.path.exists(DB_PATH):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                for k, v in live_settings.items():
                    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
                conn.commit()
                conn.close()
    except Exception as e:
        print(f"⚠️ Sozlamalar sinxronida xatolik: {e}")

    # 4. Aksiyalar (Campaigns) sinxroni
    CAMPAIGNS_BACKUP = os.path.join(DATA_DIR, "campaigns_backup.json")
    try:
        req = urllib.request.urlopen(f"{LIVE_URL}/api/campaigns", timeout=20)
        data = json.loads(req.read().decode("utf-8"))
        live_campaigns = data.get("campaigns", [])
        if live_campaigns:
            with open(CAMPAIGNS_BACKUP, "w", encoding="utf-8") as f:
                json.dump(live_campaigns, f, ensure_ascii=False, indent=2)
            print(f"✅ {len(live_campaigns)} ta aksiya zaxiraga (campaigns_backup.json) saqlandi.")
    except Exception as e:
        print(f"⚠️ Aksiyalar sinxronida xatolik: {e}")

    print("🎉 Sinxronizatsiya yakunlandi!")

if __name__ == "__main__":
    sync_live()
