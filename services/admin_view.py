import re

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
    """Professional va qulay Instagram CRM boshqaruv paneli"""
    
    # 1. Lidlar hisob-kitobi (Statistika)
    total_leads = len(clients)
    new_leads = len([c for c in clients if c.get("lead_status") in ["yangi", None, ""]])
    in_progress_leads = len([c for c in clients if c.get("lead_status") == "jarayonda"])
    done_leads = len([c for c in clients if c.get("lead_status") == "boglandi"])

    # 2. Mijozlar ro'yxati jadvali
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
            ai_card = f'''
            <div class="mb-1.5 p-2 rounded-xl bg-indigo-50/90 border border-indigo-200/80 text-indigo-950 text-xs font-medium max-w-[280px] shadow-sm">
                <div class="flex items-center gap-1 text-[11px] font-bold text-indigo-700 mb-0.5">
                    <span>💡</span> <span>AI Tahlili (Ehtiyoji):</span>
                </div>
                <div class="leading-relaxed">{ai_summary}</div>
            </div>
            '''
        else:
            ai_card = ""

        # So'rov xabari
        if last_msg and last_msg != "—":
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
            comment_block = f'''
            <div class="mt-1 p-1.5 rounded-lg bg-amber-50/90 border border-amber-200 text-amber-950 text-[11px] max-w-[220px] shadow-sm">
                <span class="font-bold text-amber-800">📝 Izoh:</span> {manager_comment}
                {f'<span class="block text-[10px] text-slate-400 mt-0.5 font-normal">{manager_time}</span>' if manager_time else ''}
            </div>
            '''

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
            </td>
        </tr>
        """

    # 3. Video Qoidalari HTML
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
                <form method="POST" action="/admin/campaign/delete" onsubmit="return confirm('Rostdan ham ushbu qoidani o\'chirmoqchimisiz?');">
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

    html = f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram CRM — Xalqaro Turizm Akademiyasi</title>
    <script src="https://cdn.tailwindcss.com"></script>
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
            <div class="flex items-center gap-3">
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
            <button onclick="switchTab('ai')" id="tab_btn_ai" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                🤖 2. Sun'iy Intellekt (AI Maslahatchi)
            </button>
            <button onclick="switchTab('campaigns')" id="tab_btn_campaigns" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                🎬 3. Video (Reels) Qoidalari <span class="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-bold">{len(campaigns)}</span>
            </button>
            <button onclick="switchTab('templates')" id="tab_btn_templates" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                💬 4. Direct Shabloni
            </button>
            <button onclick="switchTab('security')" id="tab_btn_security" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                🔐 5. Login & Parol
            </button>
        </div>

        <!-- 1-TAB: LIDLAR BAZASI (CRM) -->
        <div id="tab_leads" class="tab-content space-y-6">
            <!-- Statistika kartalari -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Jami Lidlar</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-slate-900">{total_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-amber-600 mb-1">⚪ Yangi Lidlar</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-amber-600">{new_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-indigo-600 mb-1">🟡 Jarayonda</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-indigo-600">{in_progress_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
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
                        <span class="inline-flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-2.5 rounded-xl font-medium" title="Barcha lidlar xavfsiz va doimiy saqlanadi">
                            <svg class="w-3.5 h-3.5 text-emerald-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"></path></svg>
                            <span>Doimiy saqlanadi</span>
                        </span>
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

        <!-- 2-TAB: SUN'IY INTELLEKT (AI MASLAHATCHI) -->
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

        <!-- 3-TAB: VIDEO (REELS) QOIDALARI -->
        <div id="tab_campaigns" class="tab-content hidden space-y-6">
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        🎬 3. Har Bir Video (Reels) Uchun Maxsus Qoidalar
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

        <!-- 4-TAB: DIRECT SHABLONI -->
        <div id="tab_templates" class="tab-content hidden space-y-6">
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        💬 4. Standart Direct Xabarlar Shabloni
                    </h2>
                    <p class="text-sm text-slate-500">Mijoz to'g'ridan-to'g'ri Directga yozganda bot ushbu matnlardan foydalanadi.</p>
                </div>

                <form method="POST" action="/admin/settings/save" class="space-y-6">
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

        <!-- 5-TAB: XAVFSIZLIK & LOGIN PAROL -->
        <div id="tab_security" class="tab-content hidden space-y-6">
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 max-w-2xl">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        🔐 5. CRM Xavfsizlik Sozlamalari (Login va Parol)
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

    <!-- Qidiruv va Tab almashtirish skriptlari -->
    <script>
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
    </script>
</body>
</html>
"""
    return html
