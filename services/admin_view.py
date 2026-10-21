import re
import json
from datetime import datetime, timedelta
from config import settings as config_settings

def get_login_page_html(error: str = "") -> str:
    """Zamonaviy va xavfsiz CRM kirish (Login) sahifasi"""
    error_banner = f"""
    <div class="mb-5 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-semibold flex items-center gap-2">
        <span>⚠️</span>
        <span>{error}</span>
    </div>
    """ if error else ""

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kirish | Instagram CRM — Xalqaro Turizm Akademiyasi</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}</style>
</head>
<body class="bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 min-h-screen flex items-center justify-center p-4 selection:bg-purple-500 selection:text-white">
    <div class="w-full max-w-md">
        <!-- Logo va Sarlavha -->
        <div class="text-center mb-8">
            <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-purple-600 via-pink-600 to-amber-500 flex items-center justify-center text-white text-3xl shadow-xl shadow-purple-500/20 mx-auto mb-4 border border-white/20">
                📸
            </div>
            <h1 class="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">Instagram CRM</h1>
            <p class="text-xs sm:text-sm text-indigo-200/70 mt-1 font-medium">
                Xalqaro Turizm Akademiyasi — Samarqand kampusi
            </p>
        </div>

        <!-- Forma kartasi -->
        <div class="bg-slate-900/80 backdrop-blur-xl border border-slate-800/80 rounded-3xl p-6 sm:p-8 shadow-2xl shadow-black/50">
            {error_banner}

            <form method="POST" action="/login" class="space-y-5">
                <div>
                    <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Login:</label>
                    <div class="relative">
                        <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">👤</span>
                        <input type="text" name="username" required autofocus placeholder="admin"
                            class="w-full pl-10 pr-4 py-3 bg-slate-800/70 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition">
                    </div>
                </div>

                <div>
                    <label class="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">Parol:</label>
                    <div class="relative">
                        <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">🔒</span>
                        <input type="password" name="password" required placeholder="••••••••"
                            class="w-full pl-10 pr-4 py-3 bg-slate-800/70 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition">
                    </div>
                </div>

                <button type="submit"
                    class="w-full py-3.5 px-4 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-purple-600/30 transition transform active:scale-[0.98]">
                    Tizimga Kirish 🚀
                </button>
            </form>

            <div class="mt-6 pt-5 border-t border-slate-800 text-center">
                <p class="text-xs text-slate-400">
                    Standart boshlang'ich login: <code class="text-purple-400 font-mono">admin</code> | parol: <code class="text-purple-400 font-mono">admin</code>
                </p>
            </div>
        </div>

        <p class="text-center text-xs text-slate-500 mt-6">
            © 2026 Xalqaro Turizm Akademiyasi Samarqand kampusi
        </p>
    </div>
</body>
</html>
"""

def get_admin_dashboard_html(settings: dict, campaigns: list, clients: list, recent_media: list = None, notice: str = "") -> str:
    """Professional va qulay Instagram CRM boshqaruv paneli va Analitika"""
    current_token_val = settings.get("page_access_token", "").strip() or config_settings.PAGE_ACCESS_TOKEN.strip()
    
    # ---------------- 1. LIDLAR ASOSIY HISOB-KITOBLARI ----------------
    total_leads = len(clients)
    new_leads = len([c for c in clients if c.get("lead_status") in ["yangi", None, ""]])
    in_progress_leads = len([c for c in clients if c.get("lead_status") == "jarayonda"])
    done_leads = len([c for c in clients if c.get("lead_status") == "boglandi"])
    thinking_leads = len([c for c in clients if c.get("lead_status") == "oylanyapti"])
    rejected_leads = len([c for c in clients if c.get("lead_status") == "rad"])

    conversion_rate = round((done_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

    leads_with_phone = len([c for c in clients if c.get("phone_number") and str(c.get("phone_number")).strip() not in ["", "—", "None"]])
    phone_rate = round((leads_with_phone / total_leads * 100), 1) if total_leads > 0 else 0.0

    follower_leads = len([c for c in clients if c.get("is_follower") in (1, "1", True)])
    follower_rate = round((follower_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

    followup_leads = len([c for c in clients if (c.get("followup_count") or 0) > 0])

    # ---------------- 2. SO'NGGI 14 KUNLIK VAQT DINAMIKASI ----------------
    today = datetime.now().date()
    daily_dates = [(today - timedelta(days=i)) for i in range(13, -1, -1)]
    daily_labels = [d.strftime('%d.%m') for d in daily_dates]
    daily_keys = [d.strftime('%Y-%m-%d') for d in daily_dates]

    daily_total_map = {k: 0 for k in daily_keys}
    daily_phone_map = {k: 0 for k in daily_keys}

    for c in clients:
        ca = (c.get('created_at') or '')[:10]
        if ca in daily_total_map:
            daily_total_map[ca] += 1
            if c.get("phone_number") and str(c.get("phone_number")).strip() not in ["", "—", "None"]:
                daily_phone_map[ca] += 1

    chart_daily_totals = [daily_total_map[k] for k in daily_keys]
    chart_daily_phones = [daily_phone_map[k] for k in daily_keys]

    # ---------------- 3. VIDEO VA YO'NALISHLAR (KAMPANIYALAR) TAHLILI ----------------
    campaign_stats = {}
    for c in clients:
        cmp_name = (c.get('campaign') or 'Umumiy').strip()
        if not cmp_name:
            cmp_name = 'Umumiy'
        if cmp_name not in campaign_stats:
            campaign_stats[cmp_name] = {
                "name": cmp_name,
                "total": 0,
                "phone": 0,
                "done": 0,
                "sources": set()
            }
        campaign_stats[cmp_name]["total"] += 1
        src = c.get('source') or 'Direct'
        campaign_stats[cmp_name]["sources"].add(src)
        if c.get("phone_number") and str(c.get("phone_number")).strip() not in ["", "—", "None"]:
            campaign_stats[cmp_name]["phone"] += 1
        if c.get("lead_status") == "boglandi":
            campaign_stats[cmp_name]["done"] += 1

    sorted_campaigns = sorted(campaign_stats.values(), key=lambda x: x["total"], reverse=True)
    if sorted_campaigns:
        top_campaign_labels = [sc["name"] for sc in sorted_campaigns[:6]]
        top_campaign_counts = [sc["total"] for sc in sorted_campaigns[:6]]
        top_campaign_name = sorted_campaigns[0]["name"]
        top_campaign_lead_cnt = sorted_campaigns[0]["total"]
    else:
        top_campaign_labels = ["Hozircha lid yo'q"]
        top_campaign_counts = [0]
        top_campaign_name = "Umumiy"
        top_campaign_lead_cnt = 0

    # ---------------- 4. TRAFIK MANBALARI (SOURCES) TAHLILI ----------------
    source_stats = {"Direct": 0, "Video Izohi": 0, "Boshqa": 0}
    for c in clients:
        src = (c.get('source') or 'Direct').lower()
        if any(w in src for w in ['izoh', 'komment', 'comment', 'video', 'reel', 'post']):
            source_stats["Video Izohi"] += 1
        elif 'direct' in src:
            source_stats["Direct"] += 1
        else:
            source_stats["Boshqa"] += 1

    # ---------------- 5. MENEJERLAR FAOLIYATI (LEADERBOARD) TAHLILI ----------------
    manager_stats = {}
    for c in clients:
        m_name = (c.get('manager_name') or '').strip()
        if not m_name or m_name == "—":
            m_key = "Biriktirilmagan (Yangi)"
        else:
            m_key = m_name

        if m_key not in manager_stats:
            manager_stats[m_key] = {
                "name": m_key,
                "total": 0,
                "boglandi": 0,
                "jarayonda": 0,
                "oylanyapti": 0,
                "rad": 0,
                "yangi": 0,
                "comments": 0
            }
        manager_stats[m_key]["total"] += 1
        st = c.get("lead_status") or "yangi"
        if st in manager_stats[m_key]:
            manager_stats[m_key][st] += 1
        else:
            manager_stats[m_key]["yangi"] += 1

        if c.get("manager_comment") and c.get("manager_comment").strip():
            manager_stats[m_key]["comments"] += 1

    sorted_managers = sorted(manager_stats.values(), key=lambda m: (m["boglandi"], m["total"]), reverse=True)

    # Menejerlar HTML jadvali
    managers_table_html = ""
    if not sorted_managers:
        managers_table_html = """
        <tr>
            <td colspan="8" class="px-6 py-8 text-center text-slate-400">
                Hozircha menejerlar biriktirilgan lidlar mavjud emas.
            </td>
        </tr>
        """
    for m in sorted_managers:
        m_name = m["name"]
        m_total = m["total"]
        m_done = m["boglandi"]
        m_prog = m["jarayonda"]
        m_think = m["oylanyapti"]
        m_rad = m["rad"]
        m_comm = m["comments"]
        m_conv = round((m_done / m_total * 100), 1) if m_total > 0 else 0.0

        if m_name == "Biriktirilmagan (Yangi)":
            m_avatar = "⚪"
            m_badge = f'<span class="font-medium text-slate-500 italic">{m_name}</span>'
        else:
            m_avatar = "👤"
            m_badge = f'<span class="font-bold text-slate-800">{m_name}</span>'

        managers_table_html += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50/70 transition">
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-2.5">
                    <span class="w-8 h-8 rounded-lg bg-purple-50 text-purple-700 flex items-center justify-center text-sm font-bold border border-purple-100">{m_avatar}</span>
                    {m_badge}
                </div>
            </td>
            <td class="px-4 py-3.5 text-center font-bold text-slate-800">{m_total}</td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-100">{m_done}</span>
            </td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-indigo-50 text-indigo-700">{m_prog}</span>
            </td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-amber-50 text-amber-700">{m_think}</span>
            </td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-rose-50 text-rose-700">{m_rad}</span>
            </td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center gap-1 text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md font-medium">💬 {m_comm}</span>
            </td>
            <td class="px-5 py-3.5 text-right whitespace-nowrap">
                <div class="inline-flex items-center gap-2">
                    <span class="font-bold text-xs text-emerald-700">{m_conv}%</span>
                    <div class="w-16 bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div class="bg-emerald-500 h-2 rounded-full" style="width: {min(m_conv, 100)}%"></div>
                    </div>
                </div>
            </td>
        </tr>
        """

    # Kampaniyalar HTML jadvali
    campaigns_table_html = ""
    if not sorted_campaigns:
        campaigns_table_html = """
        <tr>
            <td colspan="6" class="px-6 py-8 text-center text-slate-400">
                Hozircha kampaniyalar bo'yicha lidlar mavjud emas.
            </td>
        </tr>
        """
    for c_stat in sorted_campaigns:
        c_name = c_stat["name"]
        c_total = c_stat["total"]
        c_phone = c_stat["phone"]
        c_done = c_stat["done"]
        c_sources = ", ".join(sorted(list(c_stat["sources"]))) if c_stat["sources"] else "Direct"
        c_phone_pct = round((c_phone / c_total * 100), 1) if c_total > 0 else 0.0
        c_conv = round((c_done / c_total * 100), 1) if c_total > 0 else 0.0

        campaigns_table_html += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50/70 transition">
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-2">
                    <span class="text-base">🎬</span>
                    <span class="font-bold text-slate-800">{c_name}</span>
                </div>
            </td>
            <td class="px-4 py-3.5 text-xs text-slate-500 whitespace-nowrap">{c_sources}</td>
            <td class="px-4 py-3.5 text-center font-bold text-slate-900">{c_total} ta</td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-100">
                    📞 {c_phone} ({c_phone_pct}%)
                </span>
            </td>
            <td class="px-4 py-3.5 text-center font-bold text-slate-800">{c_done} ta</td>
            <td class="px-5 py-3.5 text-right whitespace-nowrap">
                <div class="inline-flex items-center gap-2">
                    <span class="font-bold text-xs text-indigo-700">{c_conv}%</span>
                    <div class="w-16 bg-slate-100 h-2 rounded-full overflow-hidden">
                        <div class="bg-indigo-600 h-2 rounded-full" style="width: {min(c_conv, 100)}%"></div>
                    </div>
                </div>
            </td>
        </tr>
        """

    # ---------------- 6. MIJOZLAR JADVALI QATORLARI ----------------
    clients_html = ""
    if not clients:
        clients_html = """
        <tr id="empty_row">
            <td colspan="9" class="px-6 py-12 text-center text-slate-400">
                <div class="text-4xl mb-2">📭</div>
                <div class="font-medium text-slate-600">Hozircha lidlar yo'q</div>
                <div class="text-xs text-slate-400 mt-1">Instagram Direct yoki izohlardan mijozlar yozishi bilan bu yerda paydo bo'ladi.</div>
            </td>
        </tr>
        """
    for client in clients:
        client_id = client.get('id', 0)
        full_name = client.get('full_name') or "Kiritilmagan"
        username = client.get('username') or ""
        ig_id = client.get('instagram_id') or ""
        phone = client.get('phone_number') or "—"
        source = client.get('source') or "Direct"
        campaign = client.get('campaign') or "Umumiy"
        last_msg = client.get('last_message') or "—"
        created_at = client.get('created_at', '')[:16].replace("T", " ")
        lead_status = client.get('lead_status', 'yangi')
        manager_name = client.get('manager_name') or "—"
        manager_time = client.get('manager_time') or ""
        is_fol = client.get('is_follower')
        ai_summary = client.get('ai_summary') or ""
        manager_comment = client.get('manager_comment') or ""

        digits = re.sub(r"\D", "", phone)
        tg_link = f"https://t.me/+{digits}" if len(digits) >= 9 else ""

        # Instagram profil nishoni
        if username:
            ig_badge = f'<a href="https://instagram.com/{username}" target="_blank" class="inline-flex items-center gap-1 text-[11px] font-semibold text-pink-600 hover:text-pink-700 bg-pink-50 hover:bg-pink-100 border border-pink-200 px-2 py-0.5 rounded-md transition mt-1" title="Instagram profilini ochish">📸 @{username} ↗</a>'
        else:
            ig_badge = f'<span class="text-[11px] text-slate-400 font-mono mt-0.5 block">ID: {ig_id}</span>'

        # Obuna holati
        if is_fol == 1 or is_fol is True:
            fol_badge = '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">⭐ Obunachi</span>'
        elif is_fol == 0 or is_fol is False:
            fol_badge = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-500">Obuna emas</span>'
        else:
            fol_badge = '<span class="text-xs text-slate-400">—</span>'

        # AI Ehtiyoj Tahlili kartasi
        if ai_summary:
            ai_card = f"""
            <div class="mb-1.5 p-2 rounded-xl bg-indigo-50/90 border border-indigo-200/80 text-indigo-950 text-xs font-medium max-w-[280px] shadow-sm">
                <div class="flex items-center gap-1 text-[11px] font-bold text-indigo-700 mb-0.5">
                    <span>💡</span> <span>AI Tahlili (Ehtiyoji):</span>
                </div>
                <div class="leading-relaxed">{ai_summary}</div>
            </div>
            """
        else:
            ai_card = ""

        # So'rov xabari
        if last_msg and last_msg != "—":
            if str(last_msg).startswith("🎙️"):
                voice_clean = str(last_msg).replace("🎙️", "").strip()
                last_msg_html = f"""
                <div class="max-w-[280px]">
                    <span class="inline-flex items-center gap-1 text-[10px] font-bold text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded mb-0.5">🎙️ Ovozli xabar</span>
                    <div class="text-xs text-slate-700 italic truncate" title="{voice_clean}">"{voice_clean}"</div>
                </div>
                """
            else:
                last_msg_html = f'<div class="text-xs text-slate-500 italic max-w-[280px] truncate" title="{last_msg}">"{last_msg}"</div>'
        else:
            last_msg_html = '<span class="text-xs text-slate-400">—</span>'

        if lead_status == "jarayonda":
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">🟡 Jarayonda</span>'
        elif lead_status == "boglandi":
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">🟢 Bog\'lanildi</span>'
        elif lead_status == "oylanyapti":
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">💭 O\'ylayapti</span>'
        elif lead_status == "rad":
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">🔴 Rad / Ko\'tarmadi</span>'
        else:
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">⚪ Yangi</span>'

        tg_btn = f'<a href="{tg_link}" target="_blank" class="inline-flex items-center gap-1 text-[11px] text-blue-600 bg-blue-50 hover:bg-blue-100 border border-blue-200 px-2 py-0.5 rounded font-medium transition" title="Telegramda ochish">✈️ Telegram</a>' if tg_link else ""
        call_btn = f'<a href="tel:{phone}" class="inline-flex items-center gap-1 text-[11px] text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-2 py-0.5 rounded font-medium transition" title="Qo\'ng\'iroq qilish">📞 Tel</a>' if len(digits) >= 9 else ""

        # Mutaxassis izohi kartasi va tugmasi
        escaped_comment = manager_comment.replace("\\", "\\\\").replace("'", "\\'").replace('"', '&quot;').replace('\n', ' ')
        escaped_name = full_name.replace("\\", "\\\\").replace("'", "\\'").replace('"', '&quot;')

        comment_block = ""
        if manager_comment:
            comment_block = f"""
            <div class="mt-1 p-1.5 rounded-lg bg-amber-50/90 border border-amber-200 text-amber-950 text-[11px] max-w-[220px] shadow-sm">
                <span class="font-bold text-amber-800">📝 Izoh:</span> {manager_comment}
                {f'<span class="block text-[10px] text-slate-400 mt-0.5 font-normal">{manager_time}</span>' if manager_time else ''}
            </div>
            """

        initials = (full_name[:2] if full_name and full_name != 'Kiritilmagan' else 'IG').upper()

        clients_html += f"""
        <tr class="client-row border-b border-slate-100 hover:bg-slate-50/80 transition"
            data-search="{full_name.lower()} {phone.lower()} {username.lower()} {campaign.lower()} {last_msg.lower()} {ai_summary.lower()} {manager_comment.lower()}"
            data-status="{lead_status}">
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-purple-600 via-pink-600 to-amber-500 flex items-center justify-center text-white text-xs font-bold shadow-sm flex-shrink-0">
                        {initials}
                    </div>
                    <div>
                        <div class="font-bold text-slate-900 leading-snug">{full_name}</div>
                        {ig_badge}
                    </div>
                </div>
            </td>
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div class="font-mono text-xs font-bold text-slate-800">{phone}</div>
                <div class="flex items-center gap-1.5 mt-1">
                    {tg_btn}
                    {call_btn}
                </div>
            </td>
            <td class="px-5 py-3.5 whitespace-nowrap">
                <span class="bg-purple-50 text-purple-700 border border-purple-100 px-2.5 py-0.5 rounded-md text-xs font-semibold">{campaign}</span>
                <div class="text-[11px] text-slate-400 mt-0.5">{source}</div>
            </td>
            <td class="px-5 py-3.5">
                {ai_card}
                {last_msg_html}
            </td>
            <td class="px-5 py-3.5 whitespace-nowrap">{fol_badge}</td>
            <td class="px-5 py-3.5 whitespace-nowrap">{badge_html}</td>
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div class="text-xs font-bold text-slate-800">{manager_name}</div>
                {comment_block}
                <button type="button" onclick="openCommentModal('{client_id}', '{escaped_comment}', '{escaped_name}')" class="mt-1 text-[11px] font-semibold text-purple-600 hover:text-purple-800 bg-purple-50 hover:bg-purple-100 border border-purple-200 px-2 py-0.5 rounded-md transition inline-flex items-center gap-1">
                    💬 {"Izohni o'zgartirish" if manager_comment else "Izoh qo'shish"}
                </button>
            </td>
            <td class="px-5 py-3.5 text-xs text-slate-400 whitespace-nowrap">{created_at}</td>
            <td class="px-5 py-3.5 text-right whitespace-nowrap">
                <div class="inline-flex items-center gap-1.5">
                    <form method="POST" action="/admin/clients/{client_id}/status" class="inline-flex items-center gap-1">
                        <select name="status" class="text-xs py-1 px-2 border rounded-lg bg-white border-slate-200 text-slate-700 outline-none focus:ring-1 focus:ring-purple-500">
                            <option value="yangi" {'selected' if lead_status=='yangi' else ''}>⚪ Yangi</option>
                            <option value="jarayonda" {'selected' if lead_status=='jarayonda' else ''}>🟡 Jarayonda</option>
                            <option value="boglandi" {'selected' if lead_status=='boglandi' else ''}>🟢 Bog'lanildi</option>
                            <option value="oylanyapti" {'selected' if lead_status=='oylanyapti' else ''}>💭 O'ylayapti</option>
                            <option value="rad" {'selected' if lead_status=='rad' else ''}>🔴 Rad</option>
                        </select>
                        <input type="hidden" name="manager_name" value="Admin">
                        <button type="submit" class="text-xs bg-slate-100 hover:bg-slate-200 px-2 py-1 rounded-lg border border-slate-200 text-slate-600 transition" title="Saqlash">💾</button>
                    </form>
                    <form method="POST" action="/admin/clients/{client_id}/delete" onsubmit="return confirm('Haqiqatan ham ushbu lidni o\\'chirmoqchimisiz?')" class="inline">
                        <button type="submit" class="text-xs bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 px-2 py-1 rounded-lg transition" title="Lidni o'chirish">🗑️</button>
                    </form>
                </div>
            </td>
        </tr>
        """

    # ---------------- 7. VIDEO QOIDALARI JADVALI ----------------
    campaigns_html = ""
    if not campaigns:
        campaigns_html = """
        <tr>
            <td colspan="6" class="px-6 py-8 text-center text-slate-400">
                Hozircha maxsus video qoidalari yo'q. Quyidagi forma orqali yangi aksiya qo'shishingiz mumkin.
            </td>
        </tr>
        """
    for c in campaigns:
        if c.get('media_url'):
            media_display = f"""<a href="{c['media_url']}" target="_blank" class="text-xs text-purple-600 hover:text-purple-800 font-semibold flex items-center gap-1">🎬 Videoni ochish ↗</a>"""
        elif c.get('media_id'):
            media_display = f"""<span class="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded">ID: {c['media_id'][:10]}...</span>"""
        else:
            media_display = """<span class="text-xs text-slate-400 italic">Barcha videolar</span>"""

        if c.get('trigger_keyword'):
            kw_display = f"""<span class="bg-blue-50 text-blue-700 px-2.5 py-1 rounded-full text-xs font-medium">#{c['trigger_keyword']}</span>"""
        else:
            kw_display = """<span class="bg-emerald-50 text-emerald-700 px-2.5 py-1 rounded-full text-xs font-medium">✨ Barcha izohlar</span>"""

        campaigns_html += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50 transition">
            <td class="px-6 py-4 font-bold text-slate-800">{c['name']}</td>
            <td class="px-6 py-4">{media_display}</td>
            <td class="px-6 py-4">{kw_display}</td>
            <td class="px-6 py-4 text-xs text-slate-500 truncate max-w-xs">{c.get('public_reply', '—')}</td>
            <td class="px-6 py-4 text-xs text-blue-600 truncate max-w-xs"><a href="{c.get('promo_link', '#')}" target="_blank" class="hover:underline">{c.get('promo_link', '—')}</a></td>
            <td class="px-6 py-4 text-right">
                <form method="POST" action="/admin/campaign/delete" onsubmit="return confirm('Rostdan ham ushbu qoidani o\\'chirmoqchimisiz?');">
                    <input type="hidden" name="campaign_id" value="{c['id']}">
                    <button type="submit" class="text-rose-500 hover:text-rose-700 text-xs font-semibold px-2 py-1 rounded hover:bg-rose-50 transition">O'chirish</button>
                </form>
            </td>
        </tr>
        """

    media_options_html = '<option value="">-- Akkauntdagi videoni tanlang (ixtiyoriy) --</option>\n'
    if recent_media:
        for m in recent_media:
            caption = (m.get('caption') or 'Sarlavhasiz video').replace('\n', ' ').replace('"', "'")
            if len(caption) > 55:
                caption = caption[:52] + '...'
            m_type = m.get('media_type', 'POST')
            permalink = m.get('permalink', '')
            media_options_html += f'<option value="{permalink}">[{m_type}] {caption}</option>\n'

    ai_enabled = settings.get("ai_enabled", "1") == "1"
    ai_checked = "checked" if ai_enabled else ""
    ai_followup_enabled = settings.get("ai_followup_enabled", "1") == "1"
    ai_followup_checked = "checked" if ai_followup_enabled else ""
    ai_followup_delay = str(settings.get("ai_followup_delay_minutes", "30"))
    gemini_key = settings.get("gemini_api_key", "").strip()
    if ai_enabled and gemini_key:
        ai_status_badge = "bg-emerald-50 text-emerald-700 border border-emerald-200"
        ai_status_text = "● AI Faol"
    elif ai_enabled and not gemini_key:
        ai_status_badge = "bg-amber-50 text-amber-700 border border-amber-200"
        ai_status_text = "⚠️ API Kalit kiritilmagan"
    else:
        ai_status_badge = "bg-slate-100 text-slate-500 border border-slate-200"
        ai_status_text = "○ AI O'chirilgan"

    notice_banner = f"""
    <div class="mb-6 p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm font-semibold flex items-center justify-between shadow-sm">
        <span class="flex items-center gap-2">✅ {notice}</span>
    </div>
    """ if notice else ""

    admin_username = settings.get("admin_username", "admin")

    # Chart.js JSON ma'lumotlari
    json_daily_labels = json.dumps(daily_labels)
    json_daily_totals = json.dumps(chart_daily_totals)
    json_daily_phones = json.dumps(chart_daily_phones)
    json_top_campaign_labels = json.dumps(top_campaign_labels)
    json_top_campaign_counts = json.dumps(top_campaign_counts)

    html = f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram CRM — Xalqaro Turizm Akademiyasi</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        .tab-btn.active {{
            background-color: white;
            color: #1e1b4b;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
        }}
    </style>
</head>
<body class="bg-slate-50/80 min-h-screen text-slate-800">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div class="flex items-center space-x-3.5">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-pink-600 to-amber-500 flex items-center justify-center text-white font-bold text-lg shadow-md shadow-purple-500/10">
                    📸
                </div>
                <div>
                    <div class="flex items-center gap-2.5">
                        <h1 class="text-xl font-extrabold text-slate-900 tracking-tight">Instagram CRM</h1>
                        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold {ai_status_badge}">
                            {ai_status_text}
                        </span>
                    </div>
                    <p class="text-xs text-slate-500 font-medium">Xalqaro Turizm Akademiyasi (Samarqand kampusi) — Lidlar va Muloqot Boshqaruvi</p>
                </div>
            </div>
            <div class="flex items-center gap-2.5">
                <button onclick="switchTab('analytics')" class="inline-flex items-center gap-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition" title="Statistika va Tahlil">
                    📊 Statistika
                </button>
                <a href="/api/clients/csv" class="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold shadow-sm transition">
                    📥 Excel (.CSV)
                </a>
                <a href="/logout" class="inline-flex items-center gap-1.5 bg-slate-50 hover:bg-rose-50 text-slate-700 hover:text-rose-600 border border-slate-200 hover:border-rose-200 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition" title="Tizimdan chiqish">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"></path>
                    </svg>
                    <span>Chiqish</span>
                </a>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {notice_banner}

        <!-- CRM Bo'limlar Navigatsiyasi (Tablar) -->
        <div class="bg-slate-200/80 p-1.5 rounded-2xl flex flex-wrap gap-1 mb-6 text-sm font-semibold text-slate-600">
            <button onclick="switchTab('leads')" id="tab_btn_leads" class="tab-btn active px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                👥 1. Lidlar Bazasi <span class="bg-purple-100 text-purple-700 text-xs px-2 py-0.5 rounded-full font-bold">{total_leads}</span>
            </button>
            <button onclick="switchTab('analytics')" id="tab_btn_analytics" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                📊 2. Statistika & Tahlil
            </button>
            <button onclick="switchTab('ai')" id="tab_btn_ai" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                🤖 3. Sun'iy Intellekt (AI Maslahatchi)
            </button>
            <button onclick="switchTab('campaigns')" id="tab_btn_campaigns" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                🎬 4. Video (Reels) Qoidalari <span class="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-bold">{len(campaigns)}</span>
            </button>
            <button onclick="switchTab('templates')" id="tab_btn_templates" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                💬 5. Direct Shabloni
            </button>
            <button onclick="switchTab('security')" id="tab_btn_security" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                🔐 6. Login & Parol
            </button>
        </div>

        <!-- 1-TAB: LIDLAR BAZASI (CRM) -->
        <div id="tab_leads" class="tab-content space-y-6">
            <!-- Statistika kartalari -->
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
                <div class="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Jami Lidlar</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-slate-900">{total_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-amber-600 mb-1">⚪ Yangi Lidlar</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-amber-600">{new_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-indigo-600 mb-1">🟡 Jarayonda</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-indigo-600">{in_progress_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-purple-600 mb-1">💭 O'ylayapti</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-purple-600">{thinking_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 sm:p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-emerald-600 mb-1">🟢 Bog'lanildi</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-emerald-600">{done_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
            </div>

            <!-- Qidiruv va Filtrlash Paneli -->
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 sm:p-6">
                <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4 mb-4">
                    <div class="flex-1 relative">
                        <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">🔍</span>
                        <input type="text" id="lead_search" onkeyup="filterLeads()" placeholder="Ism, telefon yoki kurs bo'yicha qidirish..."
                            class="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 bg-slate-50 focus:bg-white transition">
                    </div>
                    <div class="flex items-center gap-3">
                        <select id="lead_filter_status" onchange="filterLeads()" class="text-xs sm:text-sm px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white font-medium text-slate-700 outline-none">
                            <option value="all">Barcha holatlar</option>
                            <option value="yangi">⚪ Yangi</option>
                            <option value="jarayonda">🟡 Jarayonda</option>
                            <option value="boglandi">🟢 Bog'lanildi</option>
                            <option value="oylanyapti">💭 O'ylayapti</option>
                            <option value="rad">🔴 Rad / Ko'tarmadi</option>
                        </select>
                    </div>
                </div>

                <!-- Lidlar Jadvali -->
                <div class="overflow-x-auto rounded-xl border border-slate-100">
                    <table class="w-full text-left text-sm" id="leads_table">
                        <thead class="bg-slate-50 text-xs font-bold uppercase text-slate-500 border-b border-slate-100 tracking-wider">
                            <tr>
                                <th class="px-5 py-3.5">Mijoz / Instagram Profil</th>
                                <th class="px-5 py-3.5">Telefon & Aloqa</th>
                                <th class="px-5 py-3.5">Qiziqqan Yo'nalishi</th>
                                <th class="px-5 py-3.5">💡 AI Tahlili & So'rovi</th>
                                <th class="px-5 py-3.5">Obuna</th>
                                <th class="px-5 py-3.5">Holati</th>
                                <th class="px-5 py-3.5">Mas'ul & Mutaxassis Izohi</th>
                                <th class="px-5 py-3.5">Vaqti</th>
                                <th class="px-5 py-3.5 text-right">Boshqarish</th>
                            </tr>
                        </thead>
                        <tbody>
                            {clients_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- 2-TAB: STATISTIKA VA TAHLIL (YANGI ANALITIKA DASHBOARD) -->
        <div id="tab_analytics" class="tab-content hidden space-y-6">
            <!-- Asosiy Sarlavha banneri -->
            <div class="bg-gradient-to-r from-purple-900 via-indigo-900 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-xl relative overflow-hidden">
                <div class="absolute -right-10 -bottom-10 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none"></div>
                <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div>
                        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md text-purple-200 text-xs font-semibold mb-3 border border-white/10">
                            <span>📊</span> <span>Analitika & Konversiya Hisoboti</span>
                        </div>
                        <h2 class="text-2xl sm:text-3xl font-extrabold tracking-tight">Akademiya Instagram Faoliyati Tahlili</h2>
                        <p class="text-indigo-200/80 text-xs sm:text-sm mt-1.5 max-w-2xl font-medium leading-relaxed">
                            Reels videolari samaradorligi, kelib tushgan lidlar dinamikasi, telefon raqami olish foizi va sotuv bo'limi menejerlari natijadorligi.
                        </p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2.5 self-start md:self-center">
                        <button onclick="window.location.reload()" class="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold backdrop-blur-md border border-white/10 transition shadow-sm" title="Ma'lumotlarni yangilash">
                            🔄 Yangilash
                        </button>
                        <button onclick="window.print()" class="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold backdrop-blur-md border border-white/10 transition shadow-sm" title="Hisobotni chop etish yoki PDF saqlash">
                            🖨️ Chop etish / PDF
                        </button>
                        <a href="/api/clients/csv" class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white text-xs font-bold shadow-lg shadow-purple-500/25 transition">
                            📥 Excel (.CSV)
                        </a>
                    </div>
                </div>
            </div>

            <!-- Asosiy Ko'rsatkichlar (KPI Kartalari) -->
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <!-- Card 1: Jami Lidlar -->
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden group hover:border-purple-300 transition">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Jami Lidlar</span>
                        <span class="w-7 h-7 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center text-sm font-bold">👥</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-slate-900">{total_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                    <div class="text-[11px] text-slate-500 mt-1.5 flex items-center gap-1 font-medium">
                        <span class="text-purple-600 font-bold">100%</span> <span>barcha lidlar</span>
                    </div>
                </div>

                <!-- Card 2: Telefon Raqamlar -->
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden group hover:border-emerald-300 transition">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-bold uppercase tracking-wider text-emerald-600">Telefonli Lidlar</span>
                        <span class="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center text-sm font-bold">📞</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-emerald-600">{leads_with_phone} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                    <div class="text-[11px] text-emerald-700 mt-1.5 flex items-center gap-1 font-medium">
                        <span class="font-bold">{phone_rate}%</span> <span>kontakt qoldirgan</span>
                    </div>
                </div>

                <!-- Card 3: Konversiya (Bog'lanildi) -->
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden group hover:border-indigo-300 transition">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-bold uppercase tracking-wider text-indigo-600">Bog'lanildi</span>
                        <span class="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center text-sm font-bold">🟢</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-indigo-600">{done_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                    <div class="text-[11px] text-indigo-700 mt-1.5 flex items-center gap-1 font-medium">
                        <span class="font-bold">{conversion_rate}%</span> <span>konversiya foizi</span>
                    </div>
                </div>

                <!-- Card 4: Eng Ommabop Video/Yo'nalish -->
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden group hover:border-amber-300 transition">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-bold uppercase tracking-wider text-amber-600">Eng Faol Mavzu</span>
                        <span class="w-7 h-7 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center text-sm font-bold">🎬</span>
                    </div>
                    <div class="text-sm font-extrabold text-slate-900 truncate" title="{top_campaign_name}">{top_campaign_name}</div>
                    <div class="text-[11px] text-amber-700 mt-1.5 flex items-center gap-1 font-medium">
                        <span class="font-bold">{top_campaign_lead_cnt} ta lid</span> <span>eng yuqori natija</span>
                    </div>
                </div>

                <!-- Card 5: Obunachilar Nisbati -->
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden group hover:border-pink-300 transition">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-bold uppercase tracking-wider text-pink-600">Obunachilar</span>
                        <span class="w-7 h-7 rounded-lg bg-pink-50 text-pink-600 flex items-center justify-center text-sm font-bold">⭐</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-pink-600">{follower_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                    <div class="text-[11px] text-pink-700 mt-1.5 flex items-center gap-1 font-medium">
                        <span class="font-bold">{follower_rate}%</span> <span>profil a'zolari</span>
                    </div>
                </div>

                <!-- Card 6: AI Qayta Eslatmalar (Follow-up) -->
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative overflow-hidden group hover:border-purple-300 transition">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs font-bold uppercase tracking-wider text-purple-600">AI Follow-up</span>
                        <span class="w-7 h-7 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center text-sm font-bold">🤖</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-purple-600">{followup_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                    <div class="text-[11px] text-purple-700 mt-1.5 flex items-center gap-1 font-medium">
                        <span>qayta eslatma berilgan</span>
                    </div>
                </div>
            </div>

            <!-- Interaktiv Grafiklar Paneli (1-qator) -->
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <!-- 1-Grafik: Kunlik Lidlar Oqimi (8 cols) -->
                <div class="lg:col-span-8 bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 pb-3 border-b border-slate-100">
                        <div>
                            <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                                <span>📈</span> <span>Lidlar Oqimi Dinamikasi (So'nggi 14 kun)</span>
                            </h3>
                            <p class="text-xs text-slate-500 mt-0.5">Kunlar kesimida barcha kelgan lidlar va telefon raqami olingan sifatli mijozlar</p>
                        </div>
                        <div class="flex items-center gap-3 text-xs font-semibold">
                            <span class="inline-flex items-center gap-1.5 text-purple-700 bg-purple-50 px-2.5 py-1 rounded-lg border border-purple-100">
                                <span class="w-2.5 h-2.5 rounded-full bg-purple-600"></span> Jami Lidlar
                            </span>
                            <span class="inline-flex items-center gap-1.5 text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-100">
                                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Telefon Raqamlar
                            </span>
                        </div>
                    </div>
                    <div class="relative w-full h-72">
                        <canvas id="chartDailyTrend"></canvas>
                    </div>
                </div>

                <!-- 2-Grafik: Lidlar Holati Funneli (4 cols) -->
                <div class="lg:col-span-4 bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div class="mb-4 pb-3 border-b border-slate-100">
                        <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                            <span>🍩</span> <span>Lidlar Holati & Funnel</span>
                        </h3>
                        <p class="text-xs text-slate-500 mt-0.5">Mijozlarning bosqichlar bo'yicha taqsimoti</p>
                    </div>
                    <div class="relative w-full h-52 flex items-center justify-center">
                        <canvas id="chartLeadStatus"></canvas>
                    </div>
                    <div class="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-100 text-xs font-medium">
                        <div class="flex items-center justify-between p-1.5 bg-slate-50 rounded-lg">
                            <span class="flex items-center gap-1 text-slate-600"><span class="w-2 h-2 rounded-full bg-slate-400"></span> Yangi:</span>
                            <span class="font-bold text-slate-800">{new_leads} ta</span>
                        </div>
                        <div class="flex items-center justify-between p-1.5 bg-indigo-50 rounded-lg">
                            <span class="flex items-center gap-1 text-indigo-700"><span class="w-2 h-2 rounded-full bg-indigo-500"></span> Jarayonda:</span>
                            <span class="font-bold text-indigo-900">{in_progress_leads} ta</span>
                        </div>
                        <div class="flex items-center justify-between p-1.5 bg-emerald-50 rounded-lg">
                            <span class="flex items-center gap-1 text-emerald-700"><span class="w-2 h-2 rounded-full bg-emerald-500"></span> Bog'lanildi:</span>
                            <span class="font-bold text-emerald-900">{done_leads} ta</span>
                        </div>
                        <div class="flex items-center justify-between p-1.5 bg-amber-50 rounded-lg">
                            <span class="flex items-center gap-1 text-amber-700"><span class="w-2 h-2 rounded-full bg-amber-500"></span> O'ylayapti:</span>
                            <span class="font-bold text-amber-900">{thinking_leads} ta</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Interaktiv Grafiklar Paneli (2-qator) -->
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <!-- 3-Grafik: Video va Yo'nalishlar Samaradorligi (7 cols) -->
                <div class="lg:col-span-7 bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div class="mb-4 pb-3 border-b border-slate-100">
                        <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                            <span>🎬</span> <span>Video va Yo'nalishlar Samaradorligi</span>
                        </h3>
                        <p class="text-xs text-slate-500 mt-0.5">Qaysi video yoki kurs eng ko'p murojaat olib kelganligi</p>
                    </div>
                    <div class="relative w-full h-64">
                        <canvas id="chartCampaigns"></canvas>
                    </div>
                </div>

                <!-- 4-Grafik: Trafik Manbalari (5 cols) -->
                <div class="lg:col-span-5 bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col justify-between">
                    <div class="mb-4 pb-3 border-b border-slate-100">
                        <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                            <span>🎯</span> <span>Trafik Manbalari Taqsimoti</span>
                        </h3>
                        <p class="text-xs text-slate-500 mt-0.5">Direct xabarlar vs Reels va Post izohlari</p>
                    </div>
                    <div class="relative w-full h-52 flex items-center justify-center">
                        <canvas id="chartSources"></canvas>
                    </div>
                    <div class="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border-slate-100 text-xs font-medium">
                        <div class="flex items-center justify-between p-2 bg-purple-50 rounded-xl border border-purple-100">
                            <span class="flex items-center gap-1 text-purple-700"><span class="w-2.5 h-2.5 rounded-full bg-purple-600"></span> Direct:</span>
                            <span class="font-bold text-purple-900">{source_stats['Direct']} ta</span>
                        </div>
                        <div class="flex items-center justify-between p-2 bg-pink-50 rounded-xl border border-pink-100">
                            <span class="flex items-center gap-1 text-pink-700"><span class="w-2.5 h-2.5 rounded-full bg-pink-500"></span> Video Izohi:</span>
                            <span class="font-bold text-pink-900">{source_stats['Video Izohi']} ta</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Menejerlar Faoliyati Jadvali (Leaderboard) -->
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-100">
                    <div>
                        <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                            <span>👔</span> <span>Menejerlar Natijadorligi va Reytingi (Leaderboard)</span>
                        </h3>
                        <p class="text-xs text-slate-500 mt-0.5">Sotuv bo'limi xodimlarining lidlar bilan ishlash ko'rsatkichlari va konversiyasi</p>
                    </div>
                    <span class="text-xs font-semibold text-slate-500 bg-slate-100 px-3 py-1.5 rounded-xl self-start sm:self-auto">
                        Jami: {len(sorted_managers)} ta guruh/menejer
                    </span>
                </div>
                <div class="overflow-x-auto rounded-xl border border-slate-100">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 border-b border-slate-100 tracking-wider">
                            <tr>
                                <th class="px-5 py-3">Menejer / Xodim</th>
                                <th class="px-4 py-3 text-center">Biriktirilgan Lidlar</th>
                                <th class="px-4 py-3 text-center">🟢 Bog'lanildi</th>
                                <th class="px-4 py-3 text-center">🟡 Jarayonda</th>
                                <th class="px-4 py-3 text-center">💭 O'ylayapti</th>
                                <th class="px-4 py-3 text-center">🔴 Rad etildi</th>
                                <th class="px-4 py-3 text-center">💬 Izohlar</th>
                                <th class="px-5 py-3 text-right">Konversiya (%)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {managers_table_html}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Kampaniyalar / Videolar bo'yicha Tahliliy Jadval -->
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-100">
                    <div>
                        <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                            <span>📊</span> <span>Mavzular & Videolar Bo'yicha Chuqurlashtirilgan Tahlil</span>
                        </h3>
                        <p class="text-xs text-slate-500 mt-0.5">Har bir video va ta'lim yo'nalishi keltirgan lidlar soni, telefon olish darajasi va yakuniy natijasi</p>
                    </div>
                </div>
                <div class="overflow-x-auto rounded-xl border border-slate-100">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 border-b border-slate-100 tracking-wider">
                            <tr>
                                <th class="px-5 py-3">Video / Yo'nalish Nomi</th>
                                <th class="px-4 py-3">Manba Turi</th>
                                <th class="px-4 py-3 text-center">Jami Lidlar</th>
                                <th class="px-4 py-3 text-center">📞 Telefonli Lidlar</th>
                                <th class="px-4 py-3 text-center">🟢 Bog'lanildi</th>
                                <th class="px-5 py-3 text-right">Konversiya Darajasi</th>
                            </tr>
                        </thead>
                        <tbody>
                            {campaigns_table_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- 3-TAB: SUN'IY INTELLEKT (AI MASLAHATCHI) -->
        <div id="tab_ai" class="tab-content hidden">
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        🤖 Sun'iy Intellekt (AI Maslahatchi — Gemini)
                    </h2>
                    <p class="text-sm text-slate-500">Mijoz har qanday savol berganda (kurslar, rahbariyat, manzil, to'lov) AI professional virtual konsyerj kabi javob beradi va telefon raqamini so'rab guruhga uzatadi.</p>
                </div>

                <form method="POST" action="/admin/ai/save" class="space-y-6">
                    <div class="space-y-3">
                        <div class="flex items-center gap-3 p-4 bg-slate-50 rounded-xl border border-slate-200">
                            <input type="checkbox" id="ai_enabled" name="ai_enabled" value="1" {ai_checked} class="w-5 h-5 text-purple-600 rounded focus:ring-purple-500 cursor-pointer">
                            <label for="ai_enabled" class="text-sm font-semibold text-slate-800 cursor-pointer select-none">
                                AI Maslahatchini faollashtirish (Direct xabarlar va video izohlariga suhbat tarixini hisobga olgan holda sun'iy intellekt javob beradi)
                            </label>
                        </div>

                        <div class="p-4 bg-purple-50/70 rounded-xl border border-purple-200 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div class="flex items-start gap-3">
                                <input type="checkbox" id="ai_followup_enabled" name="ai_followup_enabled" value="1" {ai_followup_checked} class="w-5 h-5 mt-0.5 text-purple-600 rounded focus:ring-purple-500 cursor-pointer">
                                <div>
                                    <label for="ai_followup_enabled" class="text-sm font-bold text-slate-900 cursor-pointer select-none flex items-center gap-1.5">
                                        <span>🔄</span> <span>Suhbat yakunlanmagan mijozlarga avto-eslatma (AI Follow-up)</span>
                                    </label>
                                    <p class="text-xs text-slate-500 mt-0.5">
                                        Agar mijoz yozishib, telefon raqamini qoldirmasdan to'xtab qolsa, AI belgilangan vaqtdan so'ng unga qiziqishiga mos samimiy eslatma yozib suhbatni oxiriga yetkazadi.
                                    </p>
                                </div>
                            </div>
                            <div class="flex items-center gap-2 self-end sm:self-center">
                                <label class="text-xs font-semibold text-slate-700 whitespace-nowrap">Kutish vaqti:</label>
                                <select name="ai_followup_delay_minutes" class="text-xs px-2.5 py-1.5 rounded-lg border border-purple-200 bg-white font-medium text-slate-800 outline-none">
                                    <option value="15" {'selected' if ai_followup_delay=='15' else ''}>15 daqiqa</option>
                                    <option value="30" {'selected' if ai_followup_delay=='30' else ''}>30 daqiqa</option>
                                    <option value="60" {'selected' if ai_followup_delay=='60' else ''}>1 soat</option>
                                    <option value="120" {'selected' if ai_followup_delay=='120' else ''}>2 soat</option>
                                </select>
                            </div>
                        </div>

                        <div class="p-4 bg-indigo-50/70 rounded-xl border border-indigo-200 flex items-start gap-3.5">
                            <div class="text-2xl mt-0.5">🎙️</div>
                            <div>
                                <div class="text-sm font-bold text-slate-900 flex flex-wrap items-center gap-2">
                                    <span>Ovozli xabarlar (Voice Messages) bilan ishlash</span>
                                    <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">Faol ● Gemini 3.5 Multimodal Audio</span>
                                </div>
                                <p class="text-xs text-slate-600 mt-1 leading-relaxed">
                                    Mijozlar Instagram Direct orqali audio yoki ovozli xabar yuborishganda, tizim ularni avtomatik tinglaydi, o'zbek va rus tillarida so'zma-so'z matnga aylantiradi (transkripsiya), savollariga professional javob qaytaradi hamda ovozda aytilgan telefon raqamini aniqlab Telegram va CRM ga uzatadi.
                                </p>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 gap-6">
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="block text-sm font-semibold text-slate-700">Google Gemini API Kaliti:</label>
                                <a href="https://aistudio.google.com/app/apikey" target="_blank" class="text-xs text-blue-600 hover:underline font-medium">
                                    🔑 Bepul API kalit olish (aistudio.google.com) →
                                </a>
                            </div>
                            <input type="password" name="gemini_api_key" value="{settings.get('gemini_api_key', '')}" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm font-mono" placeholder="AIzaSy...">
                            <p class="text-xs text-slate-400 mt-1">Google AI Studio dan olingan rasmiy API kalit. Tizim avtomatik eng yuqori limitli <code class="text-purple-600 font-mono">gemini-flash-lite</code> modelidan foydalanadi.</p>
                        </div>

                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1">
                                Akademiya Bilimlar Bazasi (Knowledge Base) va Yo'riqnoma:
                            </label>
                            <textarea name="ai_system_prompt" rows="12" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm font-sans leading-relaxed">{settings.get('ai_system_prompt', '')}</textarea>
                            <p class="text-xs text-slate-400 mt-1">Bu yerga akademiyangiz faoliyati, rahbariyat, yangi kurslar, manzil va qoidalar kiritiladi. AI aynan shu ma'lumotlarga asoslanadi.</p>
                        </div>
                    </div>

                    <div class="flex justify-end pt-2">
                        <button type="submit" class="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold px-6 py-2.5 rounded-xl text-sm shadow-sm transition">
                            💾 AI Sozlamalarini Saqlash
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- 4-TAB: VIDEO (REELS) QOIDALARI -->
        <div id="tab_campaigns" class="tab-content hidden space-y-6">
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        🎬 4. Har Bir Video (Reels) Uchun Maxsus Qoidalar
                    </h2>
                    <p class="text-sm text-slate-500">Mijoz ma'lum bir videongizga yoki kalit so'zga (masalan: "gid", "narx") izoh qoldirganda boshqacha matn va havola yuborish.</p>
                </div>

                <div class="overflow-x-auto rounded-xl border border-slate-100 mb-8">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-50 text-xs font-bold uppercase text-slate-500 border-b border-slate-100 tracking-wider">
                            <tr>
                                <th class="px-6 py-3.5">Aksiya / Video Nomi</th>
                                <th class="px-6 py-3.5">Bog'langan Video</th>
                                <th class="px-6 py-3.5">Kalit so'z</th>
                                <th class="px-6 py-3.5">Izohga javob</th>
                                <th class="px-6 py-3.5">Beriladigan Havola</th>
                                <th class="px-6 py-3.5 text-right">Amal</th>
                            </tr>
                        </thead>
                        <tbody>
                            {campaigns_html}
                        </tbody>
                    </table>
                </div>

                <div class="bg-slate-50 p-6 rounded-2xl border border-slate-200">
                    <h3 class="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">➕ Yangi Video Qoidasi Qo'shish</h3>
                    <form method="POST" action="/admin/campaign/create" class="space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-bold text-slate-700 mb-1">Aksiya yoki Video nomi:</label>
                                <input type="text" name="name" required class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Masalan: Gid-ekskursovod kursi">
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-700 mb-1">
                                    Trigger Kalit so'z <span class="text-slate-400 font-normal">(Bo'sh qolsa har qanday izohga ishlaydi)</span>:
                                </label>
                                <input type="text" name="trigger_keyword" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Masalan: gid (yoki bo'sh qoldiring)">
                            </div>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 bg-purple-50/60 p-4 rounded-xl border border-purple-100">
                            <div>
                                <label class="block text-xs font-bold text-purple-900 mb-1">🎬 Videolaringiz ro'yxatidan tanlang:</label>
                                <select id="video_selector" onchange="if(this.value) document.getElementById('video_url').value = this.value;" class="w-full px-4 py-2.5 rounded-xl border border-purple-200 bg-white text-sm text-slate-800">
                                    {media_options_html}
                                </select>
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-purple-900 mb-1">🔗 Yoki Instagram video havolasini qo'ying:</label>
                                <input type="text" id="video_url" name="video_url" class="w-full px-4 py-2.5 rounded-xl border border-purple-200 bg-white text-sm font-mono" placeholder="https://www.instagram.com/reel/...">
                            </div>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs font-bold text-slate-700 mb-1">Izoh ostiga ommaviy javob:</label>
                                <input type="text" name="public_reply" required class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Directingizga o'quv dasturi va narxlarini yubordik! 📩">
                            </div>
                            <div>
                                <label class="block text-xs font-bold text-slate-700 mb-1">Mijozga beriladigan maxsus havola:</label>
                                <input type="url" name="promo_link" required class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm font-mono" placeholder="https://tourism-edu.uz">
                            </div>
                        </div>

                        <div>
                            <label class="block text-xs font-bold text-slate-700 mb-1">Directga boradigan xabar:</label>
                            <textarea name="dm_welcome" rows="2" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Salom! Sizni qiziqtirgan kurs bo'yicha batafsil ma'lumot yuborishimiz uchun ismingizni yozib qoldiring:"></textarea>
                        </div>

                        <div class="flex justify-end pt-2">
                            <button type="submit" class="bg-purple-600 hover:bg-purple-700 text-white font-bold px-6 py-2.5 rounded-xl text-sm shadow-sm transition">
                                ➕ Video Qoidasini Saqlash
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <!-- 5-TAB: DIRECT SHABLONI -->
        <div id="tab_templates" class="tab-content hidden space-y-6">
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        💬 5. Instagram Ulanish & Direct Xabarlar Shabloni
                    </h2>
                    <p class="text-sm text-slate-500">Instagram Access Token va mijoz Directga yozganda bot foydalanadigan matnlar.</p>
                </div>

                <form method="POST" action="/admin/settings/save" class="space-y-6">
                    <!-- Instagram Access Token Bo'limi -->
                    <div class="bg-gradient-to-r from-purple-50/70 to-indigo-50/70 rounded-2xl border border-purple-200/80 p-5 space-y-3">
                        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div>
                                <label class="block text-sm font-bold text-slate-900 flex items-center gap-1.5">
                                    <span>🔑</span> <span>Instagram Page Access Token:</span>
                                </label>
                                <p class="text-xs text-slate-500 mt-0.5">Meta for Developers (<a href="https://developers.facebook.com" target="_blank" class="text-purple-600 underline font-semibold">developers.facebook.com</a>) dan olingan token.</p>
                            </div>
                            <button type="button" onclick="checkCurrentToken()" class="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-white hover:bg-slate-50 border border-purple-200 text-purple-700 text-xs font-bold rounded-xl shadow-xs transition cursor-pointer">
                                🔍 Tokenni tekshirish
                            </button>
                        </div>
                        <div>
                            <input type="text" id="page_access_token_input" name="page_access_token" value="{current_token_val}" class="w-full px-4 py-2.5 rounded-xl border border-purple-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-xs font-mono bg-white" placeholder="IGAA...">
                        </div>
                        <div id="token_status_box" class="hidden text-xs rounded-xl p-3 font-medium"></div>
                    </div>

                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-2">1. Salomlashish matni (Birinchi xabar):</label>
                        <textarea name="direct_welcome" rows="3" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm leading-relaxed">{settings.get('direct_welcome', '')}</textarea>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-2">2. Telefon raqam so'rash matni:</label>
                            <textarea name="ask_phone" rows="3" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm leading-relaxed">{settings.get('ask_phone', '')}</textarea>
                            <p class="text-xs text-slate-400 mt-1">Mijozning ismini chiqarish uchun: <code class="text-purple-600 font-mono">{{name}}</code> deb yozing.</p>
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-2">3. Yakuniy matn (Havola bilan yuboriladi):</label>
                            <textarea name="final_message" rows="3" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm leading-relaxed">{settings.get('final_message', '')}</textarea>
                        </div>
                    </div>

                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-2">4. Asosiy havola (Sayt / Platforma):</label>
                        <input type="url" name="default_promo_link" value="{settings.get('default_promo_link', '')}" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm font-mono" placeholder="https://tourism-edu.uz">
                    </div>

                    <div class="flex justify-end pt-2">
                        <button type="submit" class="bg-purple-600 hover:bg-purple-700 text-white font-bold px-6 py-2.5 rounded-xl text-sm shadow-sm transition">
                            💾 Direct Shabloni Saqlash
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- 6-TAB: XAVFSIZLIK & LOGIN PAROL -->
        <div id="tab_security" class="tab-content hidden space-y-6">
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 max-w-2xl">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        🔐 6. CRM Xavfsizlik Sozlamalari (Login va Parol)
                    </h2>
                    <p class="text-sm text-slate-500">Boshqaruv paneliga kirish login va parolini bu yerdan xavfsiz o'zgartirishingiz mumkin.</p>
                </div>

                <form method="POST" action="/admin/security/save" class="space-y-5">
                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1.5">Joriy Login:</label>
                        <input type="text" name="username" required value="{admin_username}" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm font-medium focus:ring-2 focus:ring-purple-500 outline-none">
                    </div>

                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1.5">Yangi Parol:</label>
                        <input type="password" name="new_password" required placeholder="Kamida 4 ta belgi" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 outline-none">
                    </div>

                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1.5">Yangi Parolni Tasdiqlang:</label>
                        <input type="password" name="confirm_password" required placeholder="Parolni qayta kiriting" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 outline-none">
                    </div>

                    <div class="pt-2">
                        <button type="submit" class="bg-slate-900 hover:bg-black text-white font-bold px-6 py-2.5 rounded-xl text-sm shadow-sm transition">
                            💾 Login va Parolni Yangilash
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </main>

    <!-- Mutaxassis Izohi Qoldirish Modali -->
    <div id="commentModal" class="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div class="flex justify-between items-center mb-3">
                <h3 class="text-base font-bold text-slate-900 flex items-center gap-2">
                    <span>📝</span> <span>Mutaxassis Izohi Qoldirish</span>
                </h3>
                <button type="button" onclick="closeCommentModal()" class="text-slate-400 hover:text-slate-600 text-2xl font-bold leading-none p-1">&times;</button>
            </div>
            <p class="text-xs text-slate-500 mb-3" id="modalClientInfo">Mijoz uchun mutaxassis izohini kiriting:</p>
            <form method="POST" id="modalCommentForm" action="">
                <textarea name="comment" id="modalCommentInput" rows="4" required class="w-full p-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none placeholder-slate-400 leading-relaxed" placeholder="Mijoz bilan nima gaplashildi, qaysi guruhga yozildi yoki qachon qayta qo'ng'iroq qilish kerak..."></textarea>
                <div class="flex items-center justify-end gap-2 mt-4">
                    <button type="button" onclick="closeCommentModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 border border-slate-200 transition">Bekor qilish</button>
                    <button type="submit" class="px-5 py-2 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-700 text-white shadow-md shadow-purple-500/20 transition">Saqlash & Telegramga yuborish 💾</button>
                </div>
            </form>
        </div>
    </div>

    <!-- JavaScript: Qidiruv, Tab almashtirish va Chart.js -->
    <script>
        let chartsInitialized = false;
        let chartInstances = {{}};

        function initOrUpdateAnalyticsCharts() {{
            if (chartsInitialized) {{
                Object.values(chartInstances).forEach(c => {{
                    if (c && typeof c.resize === 'function') c.resize();
                }});
                return;
            }}

            const dailyLabels = {json_daily_labels};
            const dailyTotals = {json_daily_totals};
            const dailyPhones = {json_daily_phones};
            const topCampaignLabels = {json_top_campaign_labels};
            const topCampaignCounts = {json_top_campaign_counts};

            // 1. Kunlik Dinamika Grafigi
            const ctxDaily = document.getElementById('chartDailyTrend');
            if (ctxDaily) {{
                chartInstances.daily = new Chart(ctxDaily, {{
                    type: 'line',
                    data: {{
                        labels: dailyLabels,
                        datasets: [
                            {{
                                label: 'Jami Lidlar',
                                data: dailyTotals,
                                borderColor: '#8b5cf6',
                                backgroundColor: 'rgba(139, 92, 246, 0.12)',
                                fill: true,
                                tension: 0.35,
                                borderWidth: 2.5,
                                pointBackgroundColor: '#8b5cf6',
                                pointRadius: 4,
                                pointHoverRadius: 6
                            }},
                            {{
                                label: 'Telefon Raqamlar',
                                data: dailyPhones,
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.08)',
                                fill: false,
                                tension: 0.35,
                                borderWidth: 2.5,
                                pointBackgroundColor: '#10b981',
                                pointRadius: 4,
                                pointHoverRadius: 6
                            }}
                        ]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{
                                backgroundColor: '#0f172a',
                                titleFont: {{ size: 12, family: "'Plus Jakarta Sans', sans-serif" }},
                                bodyFont: {{ size: 12, family: "'Plus Jakarta Sans', sans-serif" }},
                                padding: 10,
                                cornerRadius: 8
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                ticks: {{ precision: 0, font: {{ size: 11 }} }},
                                grid: {{ color: '#f1f5f9' }}
                            }},
                            x: {{
                                ticks: {{ font: {{ size: 11 }} }},
                                grid: {{ display: false }}
                            }}
                        }}
                    }}
                }});
            }}

            // 2. Lidlar Holati Funnel Grafigi
            const ctxStatus = document.getElementById('chartLeadStatus');
            if (ctxStatus) {{
                chartInstances.status = new Chart(ctxStatus, {{
                    type: 'doughnut',
                    data: {{
                        labels: ["⚪ Yangi", "🟡 Jarayonda", "🟢 Bog'lanildi", "💭 O'ylayapti", "🔴 Rad"],
                        datasets: [{{
                            data: [{new_leads}, {in_progress_leads}, {done_leads}, {thinking_leads}, {rejected_leads}],
                            backgroundColor: ['#94a3b8', '#6366f1', '#10b981', '#f59e0b', '#f43f5e'],
                            borderWidth: 2,
                            borderColor: '#ffffff'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{ cornerRadius: 8 }}
                        }},
                        cutout: '68%'
                    }}
                }});
            }}

            // 3. Video va Yo'nalishlar Gorizontal Grafigi
            const ctxCampaigns = document.getElementById('chartCampaigns');
            if (ctxCampaigns) {{
                chartInstances.campaigns = new Chart(ctxCampaigns, {{
                    type: 'bar',
                    data: {{
                        labels: topCampaignLabels,
                        datasets: [{{
                            label: 'Lidlar soni',
                            data: topCampaignCounts,
                            backgroundColor: '#8b5cf6',
                            borderRadius: 8,
                            barThickness: 20
                        }}]
                    }},
                    options: {{
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{ cornerRadius: 8 }}
                        }},
                        scales: {{
                            x: {{
                                beginAtZero: true,
                                ticks: {{ precision: 0, font: {{ size: 11 }} }},
                                grid: {{ color: '#f1f5f9' }}
                            }},
                            y: {{
                                ticks: {{ font: {{ size: 11 }} }},
                                grid: {{ display: false }}
                            }}
                        }}
                    }}
                }});
            }}

            // 4. Trafik Manbalari Grafigi
            const ctxSources = document.getElementById('chartSources');
            if (ctxSources) {{
                chartInstances.sources = new Chart(ctxSources, {{
                    type: 'doughnut',
                    data: {{
                        labels: ["Direct Xabarlar", "Video Izohlari", "Boshqa"],
                        datasets: [{{
                            data: [{source_stats['Direct']}, {source_stats['Video Izohi']}, {source_stats['Boshqa']}],
                            backgroundColor: ['#8b5cf6', '#ec4899', '#06b6d4'],
                            borderWidth: 2,
                            borderColor: '#ffffff'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                            tooltip: {{ cornerRadius: 8 }}
                        }},
                        cutout: '68%'
                    }}
                }});
            }}

            chartsInitialized = true;
        }}

        function switchTab(tabId) {{
            // Barcha tab kontentlarini yashirish
            document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
            // Barcha tugmalardan active klassini olish
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

            // Tanlangan tabni ochish
            const content = document.getElementById('tab_' + tabId);
            const btn = document.getElementById('tab_btn_' + tabId);
            if (content) content.classList.remove('hidden');
            if (btn) btn.classList.add('active');

            window.location.hash = tabId;

            // Agar Statistika tabi ochilsa chartlarni render qilish / o'lchamini to'g'rilash
            if (tabId === 'analytics') {{
                setTimeout(initOrUpdateAnalyticsCharts, 60);
            }}
        }}

        // Sahifa yuklanganda URL hash bo'yicha tabni ochish
        window.addEventListener('DOMContentLoaded', () => {{
            const hash = window.location.hash.replace('#', '');
            if (hash && document.getElementById('tab_' + hash)) {{
                switchTab(hash);
            }}
        }});

        // Lidlar jadvalida tezkor qidiruv va filtrlash
        function filterLeads() {{
            const searchVal = document.getElementById('lead_search').value.toLowerCase().trim();
            const statusVal = document.getElementById('lead_filter_status').value;
            const rows = document.querySelectorAll('.client-row');

            let visibleCount = 0;
            rows.forEach(row => {{
                const searchData = row.getAttribute('data-search') || '';
                const statusData = row.getAttribute('data-status') || '';

                const matchesSearch = !searchVal || searchData.includes(searchVal);
                const matchesStatus = (statusVal === 'all') || (statusData === statusVal);

                if (matchesSearch && matchesStatus) {{
                    row.style.display = '';
                    visibleCount++;
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}

        function openCommentModal(clientId, currentComment, clientName) {{
            document.getElementById('modalCommentForm').action = '/admin/clients/' + clientId + '/comment';
            document.getElementById('modalCommentInput').value = currentComment || '';
            document.getElementById('modalClientInfo').textContent = (clientName || 'Mijoz') + ' uchun mutaxassis izohini kiriting:';
            document.getElementById('commentModal').classList.remove('hidden');
            document.getElementById('modalCommentInput').focus();
        }}

        function closeCommentModal() {{
            document.getElementById('commentModal').classList.add('hidden');
        }}

        async function checkCurrentToken() {{
            const input = document.getElementById('page_access_token_input');
            const box = document.getElementById('token_status_box');
            const tokenVal = input ? input.value.trim() : '';
            if (!box) return;

            box.className = 'text-xs rounded-xl p-3 font-medium bg-blue-50 text-blue-700 border border-blue-200 block';
            box.innerHTML = '⏳ Meta API orqali token holati tekshirilmoqda...';

            try {{
                const resp = await fetch('/api/check-token?token=' + encodeURIComponent(tokenVal));
                const data = await resp.json();
                if (data.ok) {{
                    box.className = 'text-xs rounded-xl p-3 font-medium bg-emerald-50 text-emerald-800 border border-emerald-200 block';
                    box.innerHTML = '✅ <b>Token 100% Faol!</b> Akkaunt: <b>@' + (data.username || '') + '</b> (' + (data.name || '') + ') | ID: ' + (data.id || '');
                }} else {{
                    box.className = 'text-xs rounded-xl p-3 font-medium bg-rose-50 text-rose-800 border border-rose-200 block';
                    box.innerHTML = '❌ <b>Token nofaol yoki bloklangan:</b> ' + (data.error || 'Xatolik') + '<br><span class="text-[11px] text-rose-600 mt-1 block">👉 developers.facebook.com dan yangi token olib, shu yerga qo\'ying va pastdagi "Direct Shabloni Saqlash" tugmasini bosing.</span>';
                }}
            }} catch (e) {{
                box.className = 'text-xs rounded-xl p-3 font-medium bg-rose-50 text-rose-800 border border-rose-200 block';
                box.innerHTML = '⚠️ Server bilan bog\'lanishda xatolik: ' + e.message;
            }}
        }}
    </script>
</body>
</html>
"""
    return html
