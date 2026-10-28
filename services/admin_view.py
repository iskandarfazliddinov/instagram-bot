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
                    Admin: <code class="text-purple-400 font-mono">admin</code> | Operator: <code class="text-blue-400 font-mono">operator</code>
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

def safe_js_str(val) -> str:
    if not val:
        return ""
    cleaned = str(val).replace("\\", "\\\\").replace("'", "\\'").replace('"', '&quot;').replace("\r", " ").replace("\n", " ")
    return " ".join(cleaned.split())

def get_admin_dashboard_html(settings: dict, campaigns: list, clients: list, recent_media: list = None, notice: str = "", user_role: str = "admin", current_user: dict = None, operators: list = None, activity_logs: list = None) -> str:
    """Professional va qulay Instagram CRM boshqaruv paneli va Analitika"""
    is_operator = (user_role == "operator")
    is_supervisor = (user_role == "supervisor")
    is_admin = (user_role == "admin")
    if current_user is None:
        current_user = {
            "username": "admin" if user_role == "admin" else ("jasurraxmanov" if user_role == "supervisor" else "operator"),
            "role": user_role,
            "display_name": "Admin" if user_role == "admin" else ("Jasur Raxmanov" if user_role == "supervisor" else "Operator")
        }
    if operators is None:
        operators = []
    if activity_logs is None:
        activity_logs = []

    curr_display_name = current_user.get("display_name", "Admin")

    def find_matching_operator(manager_val: str):
        if not manager_val or manager_val in ["—", "none", "", "Biriktirilmagan (Yangi)"]:
            return None
        m = str(manager_val).lower().replace("@", "").strip()
        for op in operators:
            op_u = (op.get("username") or "").lower().strip()
            op_d = (op.get("display_name") or "").lower().strip()
            if m == op_u or m == op_d:
                return op
            if op_u and (op_u in m or m in op_u):
                return op
            if op_d and (op_d in m or m in op_d or op_d.replace(" ", "_") in m or m.replace("_", " ") in op_d):
                return op
        return None

    # Har bir operatorga biriktirilgan lidlar soni (aniq va moslashtirilgan hisob)
    op_lead_counts = {}
    for op in operators:
        k = op.get("display_name") or op.get("username")
        op_lead_counts[k] = 0

    for c in clients:
        m = (c.get("manager_name") or "").strip()
        if m:
            matched_op = find_matching_operator(m)
            if matched_op:
                k = matched_op.get("display_name") or matched_op.get("username")
                op_lead_counts[k] = op_lead_counts.get(k, 0) + 1
            else:
                op_lead_counts[m] = op_lead_counts.get(m, 0) + 1

    operators_options_html = '<option value="Admin">👑 Admin</option>'
    for op in operators:
        d_name = op.get("display_name") or op.get("username")
        operators_options_html += f'<option value="{d_name}">👤 {d_name} (@{op.get("username")})</option>'

    operators_filter_options_html = '<option value="admin">👑 Admin</option>'
    for op in operators:
        d_name = op.get("display_name") or op.get("username")
        operators_filter_options_html += f'<option value="{d_name.lower()}">👤 {d_name}</option>'

    current_token_val = settings.get("page_access_token", "").strip() or config_settings.PAGE_ACCESS_TOKEN.strip()

    from database import AVAILABLE_DIRECTIONS
    dir_dict = {d["key"]: d for d in AVAILABLE_DIRECTIONS}
    if "hotel" in dir_dict:
        dir_dict["hotel_operations"] = dir_dict["hotel"]

    # Operator yo'nalishlari va filtrlash
    op_allowed_dirs_raw = (current_user.get("allowed_directions") or "all").strip() if current_user else "all"
    is_restricted_operator = (is_operator and op_allowed_dirs_raw != "all" and op_allowed_dirs_raw != "")
    allowed_dirs_set = set([k.strip() for k in op_allowed_dirs_raw.split(",") if k.strip()]) if is_restricted_operator else set()

    # Kurslar filtri (lead_filter_course) select variantlari
    if is_restricted_operator:
        course_filter_options_html = '<option value="all">📚 Mening biriktirilgan yo\'nalishlarim</option>'
        for d in AVAILABLE_DIRECTIONS:
            if d["key"] in allowed_dirs_set:
                course_filter_options_html += f'<option value="{d["key"]}">{d["name"]}</option>'
    else:
        course_filter_options_html = '<option value="all">📚 Barcha yo\'nalishlar</option>'
        for d in AVAILABLE_DIRECTIONS:
            course_filter_options_html += f'<option value="{d["key"]}">{d["name"]}</option>'

    # Xodim uchun yo'nalishlar xabarnomasi banneri
    operator_directions_banner = ""
    if is_restricted_operator:
        b_pills = []
        for k in op_allowed_dirs_raw.split(","):
            k = k.strip()
            if k in dir_dict:
                b_pills.append(f'<span class="px-2 py-0.5 rounded-lg bg-purple-100 text-purple-800 font-bold border border-purple-200">{dir_dict[k]["short"]}</span>')
        pills_html = " ".join(b_pills)
        operator_directions_banner = f"""
        <div class="mb-4 p-3.5 bg-gradient-to-r from-purple-50 via-indigo-50 to-blue-50 border border-purple-200 rounded-2xl flex flex-wrap items-center justify-between gap-3 text-xs shadow-xs">
            <div class="flex flex-wrap items-center gap-2 text-purple-950 font-bold">
                <span class="text-base">🎯</span>
                <span>Sizga biriktirilgan yo'nalishlar:</span>
                <div class="flex flex-wrap gap-1.5">{pills_html}</div>
            </div>
            <span class="text-slate-500 font-medium bg-white/80 px-2.5 py-1 rounded-lg border border-purple-100">🔒 Faqat sizga tegishli lidlar ko'rsatilmoqda</span>
        </div>
        """

    new_op_dir_checkboxes = ""
    for d in AVAILABLE_DIRECTIONS:
        new_op_dir_checkboxes += f"""
        <label class="flex items-center gap-2 p-1.5 hover:bg-slate-100/70 rounded-lg cursor-pointer text-slate-700">
            <input type="checkbox" name="directions" value="{d['key']}" class="new-op-dir-check rounded text-purple-600">
            <span>{d['name']}</span>
        </label>
        """

    modal_dir_checkboxes = ""
    for d in AVAILABLE_DIRECTIONS:
        modal_dir_checkboxes += f"""
        <label class="flex items-center gap-2 p-2 rounded-xl border border-slate-200 hover:border-purple-300 hover:bg-purple-50/50 cursor-pointer transition text-xs font-semibold text-slate-800">
            <input type="checkbox" name="directions" value="{d['key']}" class="modal-dir-check w-4 h-4 rounded text-purple-600 focus:ring-purple-500">
            <span class="truncate">{d['name']}</span>
        </label>
        """
    
    # ---------------- 1. LIDLAR ASOSIY HISOB-KITOBLARI ----------------
    total_leads = len(clients)
    new_leads = len([c for c in clients if c.get("lead_status") in ["yangi", None, ""]])
    done_leads = len([c for c in clients if c.get("lead_status") in ["boglandi", "jarayonda"]])
    thinking_leads = len([c for c in clients if c.get("lead_status") == "oylanyapti"])
    reserve_leads = len([c for c in clients if c.get("lead_status") in ["zahira", "zaxira"]])
    rejected_leads = len([c for c in clients if c.get("lead_status") == "rad"])

    conversion_rate = round((done_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

    leads_with_phone = len([c for c in clients if c.get("phone_number") and str(c.get("phone_number")).strip() not in ["", "—", "None"]])
    phone_rate = round((leads_with_phone / total_leads * 100), 1) if total_leads > 0 else 0.0

    follower_leads = len([c for c in clients if c.get("is_follower") in (1, "1", True)])
    follower_rate = round((follower_leads / total_leads * 100), 1) if total_leads > 0 else 0.0

    followup_leads = len([c for c in clients if (c.get("followup_count") or 0) > 0])

    today_str = datetime.now().strftime("%Y-%m-%d")
    month_str = datetime.now().strftime("%Y-%m")
    current_month_name = datetime.now().strftime("%B %Y")
    now_date_display = datetime.now().strftime("%d.%m.%Y")

    # Bugungi lidlar
    today_clients = [c for c in clients if (c.get("created_at") or "")[:10] == today_str]
    today_total = len(today_clients)
    today_phones = len([c for c in today_clients if c.get("phone_number") and str(c.get("phone_number")).strip() not in ["", "—", "None"]])
    today_done = len([c for c in today_clients if c.get("lead_status") == "boglandi"])
    today_conv = round((today_done / today_total * 100), 1) if today_total > 0 else 0.0

    # Oylik lidlar
    month_clients = [c for c in clients if (c.get("created_at") or "")[:7] == month_str]
    month_total = len(month_clients)
    month_phones = len([c for c in month_clients if c.get("phone_number") and str(c.get("phone_number")).strip() not in ["", "—", "None"]])
    month_done = len([c for c in month_clients if c.get("lead_status") == "boglandi"])
    month_conv = round((month_done / month_total * 100), 1) if month_total > 0 else 0.0

    # Shubhali lidlarni hisoblash (Anti-Fraud: Telefoni ham, Direct xabari ham yo'q holda 'Bog'lanildi' qilingan)
    def check_is_suspicious(client_dict):
        st = client_dict.get("lead_status") or "yangi"
        ph = str(client_dict.get("phone_number") or "").strip()
        has_ph = bool(ph and ph not in ["", "—", "None"])
        ch_raw = client_dict.get("chat_history") or "[]"
        try:
            ch = json.loads(ch_raw) if isinstance(ch_raw, str) else ch_raw
        except Exception:
            ch = []
        has_m_msg = any(m.get("role") in ["manager", "operator"] for m in ch)
        return bool(st == "boglandi" and not has_ph and not has_m_msg)

    total_suspicious = sum(1 for c in clients if check_is_suspicious(c))

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

    # ---------------- 5. MENEJERLAR FAOLIYATI (LEADERBOARD VA AUDIT) TAHLILI ----------------
    manager_stats = {}
    for op in operators:
        d_name = (op.get("display_name") or op.get("username") or "").strip()
        if d_name:
            manager_stats[d_name] = {
                "name": d_name,
                "total": 0,
                "today": 0,
                "month": 0,
                "boglandi": 0,
                "oylanyapti": 0,
                "zahira": 0,
                "rad": 0,
                "yangi": 0,
                "phones": 0,
                "direct_msgs": 0,
                "suspicious": 0,
                "comments": 0
            }

    for c in clients:
        m_name = (c.get('manager_name') or '').strip()
        matched_op = find_matching_operator(m_name)
        if matched_op:
            m_key = matched_op.get("display_name") or matched_op.get("username")
        elif not m_name or m_name == "—":
            m_key = "Biriktirilmagan (Yangi)"
        else:
            m_key = m_name

        if m_key not in manager_stats:
            manager_stats[m_key] = {
                "name": m_key,
                "total": 0,
                "today": 0,
                "month": 0,
                "boglandi": 0,
                "oylanyapti": 0,
                "zahira": 0,
                "rad": 0,
                "yangi": 0,
                "phones": 0,
                "direct_msgs": 0,
                "suspicious": 0,
                "comments": 0
            }
        manager_stats[m_key]["total"] += 1

        c_date = (c.get("created_at") or "")[:10]
        c_month = (c.get("created_at") or "")[:7]
        m_time = (c.get("manager_time") or "")
        if c_date == today_str or (today_str in m_time):
            manager_stats[m_key]["today"] += 1
        if c_month == month_str:
            manager_stats[m_key]["month"] += 1

        ph = str(c.get("phone_number") or "").strip()
        has_ph = bool(ph and ph not in ["", "—", "None"])
        if has_ph:
            manager_stats[m_key]["phones"] += 1

        ch_raw = c.get("chat_history") or "[]"
        try:
            ch_list = json.loads(ch_raw) if isinstance(ch_raw, str) else ch_raw
        except Exception:
            ch_list = []
        has_dm = any(m.get("role") in ["manager", "operator"] for m in ch_list)
        if has_dm:
            manager_stats[m_key]["direct_msgs"] += 1

        st = c.get("lead_status") or "yangi"
        if st in ["zahira", "zaxira"]:
            st = "zahira"
        elif st == "jarayonda":
            st = "boglandi"
        if st in manager_stats[m_key]:
            manager_stats[m_key][st] += 1
        else:
            manager_stats[m_key]["yangi"] += 1

        if st == "boglandi" and not has_ph and not has_dm:
            manager_stats[m_key]["suspicious"] += 1

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
        m_think = m["oylanyapti"]
        m_zahira = m["zahira"]
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
                <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-sky-50 text-sky-700">{m_think}</span>
            </td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-100">{m_done}</span>
            </td>
            <td class="px-4 py-3.5 text-center">
                <span class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold bg-indigo-50 text-indigo-700">{m_zahira}</span>
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
    clients_for_export = []
    for idx, c in enumerate(clients, start=1):
        clients_for_export.append({
            "id": c.get("id") or idx,
            "username": c.get("username") or "",
            "full_name": c.get("full_name") or "",
            "phone_number": c.get("phone_number") or "",
            "campaign": c.get("campaign") or "Umumiy",
            "source": c.get("source") or "Direct",
            "lead_status": c.get("lead_status") or "yangi",
            "is_follower": 1 if c.get("is_follower") else 0,
            "ai_summary": c.get("ai_summary") or "",
            "last_message": c.get("last_message") or "",
            "manager_name": c.get("manager_name") or "",
            "manager_comment": c.get("manager_comment") or "",
            "created_at": (c.get("created_at") or "")[:16].replace("T", " "),
            "instagram_id": str(c.get("instagram_id") or ""),
            "ai_paused": 1 if c.get("ai_paused") else 0
        })
    clients_json_data = json.dumps(clients_for_export, ensure_ascii=False).replace("</script>", "<\\/script>")

    clients_html = ""
    colspan_num = 9
    kanban_cards_dict = {
        "yangi": [],
        "oylanyapti": [],
        "boglandi": [],
        "zahira": [],
        "rad": []
    }
    if not clients:
        clients_html = f"""
        <tr id="empty_row">
            <td colspan="{colspan_num}" class="px-6 py-12 text-center text-slate-400">
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
        lead_status = client.get('lead_status', 'yangi') or 'yangi'
        if lead_status in ['zaxira', 'zahira']:
            lead_status = 'zahira'
        manager_name = client.get('manager_name') or "—"
        manager_time = client.get('manager_time') or ""
        is_fol = client.get('is_follower')
        ai_summary = client.get('ai_summary') or ""
        manager_comment = client.get('manager_comment') or ""
        ai_paused = 1 if client.get('ai_paused') else 0
        is_suspicious = check_is_suspicious(client)

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

        if lead_status in ["boglandi", "jarayonda"]:
            if is_suspicious:
                badge_html = '<div class="flex flex-col gap-1 items-start"><span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">🟢 Bog\'lanildi</span><span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300 animate-pulse" title="Anti-Fraud: Telefon raqami ham, Direct yozishmasi ham yo\'q">⚠️ Shubhali</span></div>'
            else:
                badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">🟢 Bog\'lanildi</span>'
        elif lead_status == "oylanyapti":
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">💭 O\'ylayapti</span>'
        elif lead_status == "zahira":
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800">📦 Zahira</span>'
        elif lead_status == "rad":
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">🔴 Rad / Ko\'tarmadi</span>'
        else:
            badge_html = '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">⚪ Yangi</span>'

        tg_btn = f'<a href="{tg_link}" target="_blank" class="inline-flex items-center gap-1 text-[11px] text-blue-600 bg-blue-50 hover:bg-blue-100 border border-blue-200 px-2 py-0.5 rounded font-medium transition" title="Telegramda ochish">✈️ Telegram</a>' if tg_link else ""
        call_btn = f'<a href="tel:{phone}" class="inline-flex items-center gap-1 text-[11px] text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 px-2 py-0.5 rounded font-medium transition" title="Qo\'ng\'iroq qilish">📞 Tel</a>' if len(digits) >= 9 else ""

        # Mutaxassis izohi kartasi va tugmasi
        escaped_comment = safe_js_str(manager_comment)
        escaped_name = safe_js_str(full_name)
        escaped_campaign = safe_js_str(campaign)
        escaped_manager = safe_js_str(manager_name)

        comment_block = ""
        if manager_comment:
            comment_block = f"""
            <div class="mt-1 p-1.5 rounded-lg bg-amber-50/90 border border-amber-200 text-amber-950 text-[11px] max-w-[220px] shadow-sm">
                <span class="font-bold text-amber-800">📝 Izoh:</span> {manager_comment}
                {f'<span class="block text-[10px] text-slate-400 mt-0.5 font-normal">{manager_time}</span>' if manager_time else ''}
            </div>
            """

        comment_btn = f"""
        <button type="button" id="table_row_comment_btn_{client_id}" onclick="openCommentModal('{client_id}', '{escaped_comment}', '{escaped_name}', '{lead_status}', '{phone}', '{username}', '{escaped_campaign}', '{escaped_manager}', {ai_paused}, '{ig_id}')" class="mt-1 text-[11px] font-semibold text-purple-600 hover:text-purple-800 bg-purple-50 hover:bg-purple-100 border border-purple-200 px-2 py-0.5 rounded-md transition inline-flex items-center gap-1 shadow-xs cursor-pointer" title="Bog'lanish va izoh kiritish">
            💬 {"Izohni o'zgartirish" if manager_comment else "Izoh qo'shish"}
        </button>
        """

        delete_btn = ""
        if not is_operator:
            delete_btn = f"""
            <button type="button" onclick="deleteLeadAjax('{client_id}')" class="text-xs bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 px-2 py-1 rounded-lg transition cursor-pointer" title="Lidni o'chirish">🗑️</button>
            """

        chat_pulse = '<span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" title="AI to&#39;xtatilgan (Inson nazoratida)"></span>' if ai_paused else ''
        chat_btn_td = f"""
        <button type="button" onclick="openInstagramChatModal('{client_id}', '{escaped_name}', '{username}', '{escaped_campaign}', {ai_paused}, '{ig_id}')" class="text-xs bg-pink-50 hover:bg-pink-100 text-pink-700 border border-pink-200 px-2 py-1 rounded-lg transition font-bold inline-flex items-center gap-1 shadow-2xs cursor-pointer" title="Instagram Direct Chati & Xabar yozish">
            📸 Chat {chat_pulse}
        </button>
        """

        action_td = f"""
        <td class="px-5 py-3.5 text-right whitespace-nowrap">
            <div class="inline-flex items-center gap-1.5">
                {chat_btn_td}
                <select name="status" onchange="quickMoveLead('{client_id}', this.value)" class="text-xs py-1 px-2 border rounded-lg bg-white border-slate-200 text-slate-700 outline-none focus:ring-1 focus:ring-purple-500 font-medium cursor-pointer shadow-xs" title="Holatni tanlang (avtomatik saqlanadi)">
                    <option value="yangi" {'selected' if lead_status=='yangi' else ''}>⚪ Yangi</option>
                    <option value="oylanyapti" {'selected' if lead_status=='oylanyapti' else ''}>💭 O'ylayapti</option>
                    <option value="boglandi" {'selected' if lead_status in ['boglandi', 'jarayonda'] else ''}>🟢 Bog'lanildi</option>
                    <option value="zahira" {'selected' if lead_status=='zahira' else ''}>📦 Zahira</option>
                    <option value="rad" {'selected' if lead_status=='rad' else ''}>🔴 Rad</option>
                </select>
                <button type="button" id="table_action_comment_btn_{client_id}" onclick="openCommentModal('{client_id}', '{escaped_comment}', '{escaped_name}', '{lead_status}', '{phone}', '{username}', '{escaped_campaign}', '{escaped_manager}', {ai_paused}, '{ig_id}')" class="text-xs bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 px-2 py-1 rounded-lg transition font-medium cursor-pointer" title="Bog'lanish & Izoh">💬</button>
                {delete_btn}
            </div>
        </td>
        """

        matched_op = find_matching_operator(manager_name)
        disp_mgr = matched_op.get("display_name") if matched_op else manager_name
        matched_d = (matched_op.get("display_name") or "").lower() if matched_op else ""
        matched_u = (matched_op.get("username") or "").lower() if matched_op else ""
        mgr_search_tags = f"{manager_name.lower()} {matched_d} {matched_u}".strip()

        if not manager_name or manager_name == "—":
            manager_display_badge = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold text-slate-400 bg-slate-100">⚪ Biriktirilmagan</span>'
        elif disp_mgr == curr_display_name or manager_name == curr_display_name:
            manager_display_badge = f'<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold text-purple-700 bg-purple-50 border border-purple-200 shadow-2xs">⭐ {disp_mgr} (Men)</span>'
        else:
            manager_display_badge = f'<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold text-slate-700 bg-slate-50 border border-slate-200">👤 {disp_mgr}</span>'

        initials = (full_name[:2] if full_name and full_name != 'Kiritilmagan' else 'IG').upper()

        # Kurs va Manba nishonlari (Badges)
        c_low = campaign.lower()
        if "front" in c_low or "housekeeping" in c_low or "xona tozalash" in c_low or "tourism-edu" in c_low:
            campaign_badge = '<span class="bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center gap-1.5 shadow-xs">💻 Front Office (Onlayn)</span>'
        elif "hotel" in c_low or "mehmonxona" in c_low or "operations" in c_low:
            campaign_badge = '<span class="bg-indigo-50 text-indigo-700 border border-indigo-200 px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center gap-1.5 shadow-xs">🏨 Hotel Operations</span>'
        elif "malaka" in c_low:
            campaign_badge = '<span class="bg-teal-50 text-teal-700 border border-teal-200 px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center gap-1.5 shadow-xs">🗺 Gidlik (Malaka oshirish)</span>'
        elif "gid" in c_low or "ekskurs" in c_low:
            campaign_badge = '<span class="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center gap-1.5 shadow-xs">🌍 Gidlik (Qayta tayyorlash)</span>'
        elif "turagent" in c_low:
            campaign_badge = '<span class="bg-sky-50 text-sky-700 border border-sky-200 px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center gap-1.5 shadow-xs">✈️ Turagentlik</span>'
        elif "turoperator" in c_low:
            campaign_badge = '<span class="bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center gap-1.5 shadow-xs">✈️ Turoperatorlik</span>'
        elif "onlayn" in c_low or "online" in c_low:
            campaign_badge = '<span class="bg-amber-50 text-amber-700 border border-amber-200 px-2.5 py-1 rounded-lg text-xs font-bold inline-flex items-center gap-1.5 shadow-xs">💻 Onlayn platforma</span>'
        elif "narx" in c_low:
            campaign_badge = '<span class="bg-purple-50 text-purple-700 border border-purple-200 px-2.5 py-1 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5">💰 Kurslar narxi</span>'
        elif "dastur" in c_low:
            campaign_badge = '<span class="bg-violet-50 text-violet-700 border border-violet-200 px-2.5 py-1 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5">📄 O\'quv dasturi</span>'
        elif "konsultatsiya" in c_low or "batafsil" in c_low:
            campaign_badge = '<span class="bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-lg text-xs font-semibold inline-flex items-center gap-1.5">💬 Batafsil konsultatsiya</span>'
        else:
            campaign_badge = f'<span class="bg-slate-100 text-slate-700 border border-slate-200 px-2.5 py-1 rounded-lg text-xs font-medium inline-flex items-center gap-1.5">💬 {campaign}</span>'

        s_low = source.lower()
        if "instagram.com/reel/" in s_low or "instagram.com/p/" in s_low:
            m_url = re.search(r'https?://[^\s]+', source)
            url_found = m_url.group(0) if m_url else "#"
            video_label = "🎬 Reels izohi ↗"
            if "dbm6ein" in s_low:
                video_label = "🎬 Front Office Reels ↗"
            elif "dezbpoz" in s_low or "derpzsn" in s_low:
                video_label = "🎬 Hotel Ops Reels ↗"
            elif "dbdpnkl" in s_low:
                video_label = "🎬 Gidlik Reels ↗"
            elif "dcqteak" in s_low:
                video_label = "🎬 Turagent Reels ↗"
            elif "dbxj3f" in s_low:
                video_label = "🎬 Turoperator Reels ↗"
            source_badge = f'<a href="{url_found}" target="_blank" class="inline-flex items-center gap-1 text-[11px] font-bold text-rose-600 hover:text-rose-700 hover:underline mt-1 bg-rose-50 px-2 py-0.5 rounded border border-rose-100 shadow-2xs" title="Instagram videoni ko\'rish">{video_label}</a>'
        elif "reel" in s_low or "video" in s_low:
            source_badge = '<div class="inline-flex items-center gap-1 text-[11px] font-medium text-rose-600 mt-1 bg-rose-50 px-2 py-0.5 rounded border border-rose-100">🎬 Video izohi</div>'
        else:
            source_badge = '<div class="inline-flex items-center gap-1 text-[11px] text-slate-500 mt-1">💬 Direct</div>'

        clients_html += f"""
        <tr class="client-row border-b border-slate-100 hover:bg-slate-50/80 transition"
            data-client-id="{client_id}"
            data-search="{full_name.lower()} {phone.lower()} {username.lower()} {campaign.lower()} {source.lower()} {last_msg.lower()} {ai_summary.lower()} {manager_comment.lower()} {manager_name.lower()}"
            data-status="{lead_status}"
            data-course="{campaign.lower()}"
            data-source="{source.lower()}"
            data-manager="{mgr_search_tags}"
            data-suspicious="{1 if is_suspicious else 0}">
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
                <div class="font-mono text-xs font-bold text-slate-800" id="row_phone_{client_id}">{phone}</div>
                <div class="flex items-center gap-1.5 mt-1">
                    {tg_btn}
                    {call_btn}
                </div>
            </td>
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div>{campaign_badge}</div>
                <div>{source_badge}</div>
            </td>
            <td class="px-5 py-3.5">
                {ai_card}
                {last_msg_html}
            </td>
            <td class="px-5 py-3.5 whitespace-nowrap">{fol_badge}</td>
            <td class="px-5 py-3.5 whitespace-nowrap" id="row_status_badge_{client_id}">{badge_html}</td>
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div id="row_manager_{client_id}">{manager_display_badge}</div>
                <div id="row_comment_wrap_{client_id}">{comment_block}</div>
                <div id="row_comment_btn_wrap_{client_id}">{comment_btn}</div>
            </td>
            <td class="px-5 py-3.5 text-xs text-slate-400 whitespace-nowrap">{created_at}</td>
            {action_td}
        </tr>
        """

        target_status = lead_status if lead_status in kanban_cards_dict else ("boglandi" if lead_status == "jarayonda" else "yangi")

        kanban_ai_or_msg = ""
        if ai_summary:
            kanban_ai_or_msg = f"""
            <div class="mb-2 p-2 rounded-xl bg-indigo-50/90 border border-indigo-200/80 text-indigo-950 text-xs shadow-2xs">
                <div class="flex items-center gap-1 text-[10px] font-bold text-indigo-700 mb-0.5">
                    <span>💡</span> <span>AI Tahlili:</span>
                </div>
                <div class="text-[11px] leading-snug line-clamp-3">{ai_summary}</div>
            </div>
            """
        elif last_msg and last_msg != "—":
            if str(last_msg).startswith("🎙️"):
                voice_clean = str(last_msg).replace("🎙️", "").strip()
                kanban_ai_or_msg = f"""
                <div class="mb-2 p-1.5 rounded-lg bg-purple-50 border border-purple-100 text-[11px] text-purple-900">
                    <span class="font-bold text-[10px] text-purple-700 block">🎙️ Ovozli xabar:</span>
                    <span class="italic line-clamp-2">"{voice_clean}"</span>
                </div>
                """
            else:
                kanban_ai_or_msg = f"""
                <div class="mb-2 text-[11px] text-slate-600 bg-slate-50 p-1.5 rounded-lg border border-slate-100 italic line-clamp-2" title="{last_msg}">
                    "{last_msg}"
                </div>
                """

        kanban_comment_block = ""
        if manager_comment:
            kanban_comment_block = f"""
            <div class="p-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-950 text-[11px] shadow-2xs mt-1">
                <span class="font-bold text-amber-800">📝 Izoh:</span> {manager_comment}
                {f'<span class="block text-[10px] text-slate-400 mt-0.5 font-normal">{manager_time}</span>' if manager_time else ''}
            </div>
            """

        kanban_suspicious_banner = ""
        if is_suspicious:
            kanban_suspicious_banner = """
            <div class="mb-2 p-1.5 rounded-lg bg-rose-50 border border-rose-300 text-rose-900 text-[10px] font-bold flex items-center justify-between shadow-2xs">
                <span>⚠️ Shubhali Bog'lanish</span>
                <span class="text-[9px] text-rose-600 font-semibold">Telefon/Direct yo'q</span>
            </div>
            """

        kanban_cards_dict[target_status].append(f"""
        <div class="kanban-card bg-white rounded-xl p-3 border border-slate-200/90 hover:border-purple-300 hover:shadow-md transition shadow-xs cursor-grab active:cursor-grabbing relative group select-none"
             id="kanban_card_{client_id}"
             draggable="true"
             ondragstart="handleDragStart(event, '{client_id}', '{lead_status}')"
             ondragend="handleDragEnd(event, '{client_id}')"
             data-client-id="{client_id}"
             data-search="{full_name.lower()} {phone.lower()} {username.lower()} {campaign.lower()} {source.lower()} {last_msg.lower()} {ai_summary.lower()} {manager_comment.lower()} {manager_name.lower()}"
             data-status="{lead_status}"
             data-course="{campaign.lower()}"
             data-source="{source.lower()}"
             data-manager="{mgr_search_tags}"
             data-suspicious="{1 if is_suspicious else 0}">

            <!-- Top row: Avatar, Name, Ig link, and Date -->
            <div class="flex items-start justify-between gap-1.5 mb-2">
                <div class="flex items-center gap-2 min-w-0">
                    <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 via-pink-600 to-amber-500 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-2xs">
                        {initials}
                    </div>
                    <div class="min-w-0">
                        <div class="font-bold text-xs text-slate-900 truncate" title="{full_name}">{full_name}</div>
                        {ig_badge}
                    </div>
                </div>
                <div class="text-right shrink-0">
                    <span class="text-[10px] text-slate-400 block font-mono">{created_at[-5:] if len(created_at) >= 5 else ''}</span>
                    {fol_badge}
                </div>
            </div>

            {kanban_suspicious_banner}

            <!-- Phone & Quick Contact Buttons -->
            <div class="flex items-center justify-between gap-1.5 py-1 px-2 bg-slate-50 rounded-lg border border-slate-100 mb-2">
                <div class="text-xs font-mono font-bold text-slate-800 truncate" id="kanban_phone_{client_id}">
                    {phone if phone and phone != '—' else '<span class="text-slate-400 font-sans italic text-[11px] font-normal">Raqamsiz</span>'}
                </div>
                <div class="flex items-center gap-1 shrink-0">
                    {call_btn}
                    {tg_btn}
                </div>
            </div>

            <!-- Course & Source badges -->
            <div class="flex flex-wrap items-center gap-1 mb-2">
                {campaign_badge}
                {source_badge}
            </div>

            <!-- AI summary or Last message -->
            {kanban_ai_or_msg}

            <!-- Manager & Comment -->
            <div class="pt-2 border-t border-slate-100 flex flex-col gap-1">
                <div class="flex items-center justify-between text-[11px]">
                    <span class="text-slate-400 text-[10px] font-medium">Mas'ul:</span>
                    <span id="kanban_manager_{client_id}">{manager_display_badge}</span>
                </div>
                <div id="kanban_comment_wrap_{client_id}">
                    {kanban_comment_block}
                </div>
            </div>

            <!-- Card Actions footer: Direct Chat + Izoh modal button + Quick status move dropdown -->
            <div class="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between gap-1.5">
                <button type="button" onclick="openInstagramChatModal('{client_id}', '{escaped_name}', '{username}', '{escaped_campaign}', {ai_paused}, '{ig_id}')"
                        class="py-1 px-2 bg-pink-50 hover:bg-pink-100 text-pink-700 border border-pink-200 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1 shadow-2xs cursor-pointer" title="Instagram Direct Chati">
                    📸 Chat {'<span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse"></span>' if ai_paused else ''}
                </button>
                <button type="button" id="kanban_comment_btn_{client_id}" onclick="openCommentModal('{client_id}', '{escaped_comment}', '{escaped_name}', '{lead_status}', '{phone}', '{username}', '{escaped_campaign}', '{escaped_manager}', {ai_paused}, '{ig_id}')"
                        class="flex-1 py-1 px-2 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 rounded-lg text-xs font-bold transition flex items-center justify-center gap-1 shadow-2xs cursor-pointer" title="Bog'lanish & Izoh">
                    💬 Izoh
                </button>
                <select onchange="quickMoveLead('{client_id}', this.value)" class="text-[11px] py-1 px-1.5 bg-white border border-slate-200 rounded-lg text-slate-700 font-semibold outline-none focus:ring-1 focus:ring-purple-500 cursor-pointer shadow-2xs" title="Boshqa ustunga ko'chirish">
                    <option value="yangi" {'selected' if lead_status=='yangi' else ''}>⚪ Yangi</option>
                    <option value="oylanyapti" {'selected' if lead_status=='oylanyapti' else ''}>💭 O'ylayapti</option>
                    <option value="boglandi" {'selected' if lead_status in ['boglandi', 'jarayonda'] else ''}>🟢 Bog'landi</option>
                    <option value="zahira" {'selected' if lead_status=='zahira' else ''}>📦 Zahira</option>
                    <option value="rad" {'selected' if lead_status=='rad' else ''}>🔴 Rad</option>
                </select>
            </div>
        </div>
        """)

    # ---------------- 6.5 KANBAN USTUNLARI (PIPELINE) TUZISH ----------------
    columns_meta = [
        {
            "status": "yangi",
            "title": "Yangi Lidlar",
            "icon": "⚪",
            "subtitle": "Bog'lanish kutilmoqda",
            "border": "border-slate-300",
            "header_bg": "bg-slate-100 text-slate-800 border border-slate-200",
            "badge_cls": "bg-slate-200 text-slate-800"
        },
        {
            "status": "oylanyapti",
            "title": "O'ylayapti",
            "icon": "💭",
            "subtitle": "Keyinroq bog'laniladi",
            "border": "border-sky-300",
            "header_bg": "bg-sky-100 text-sky-900 border border-sky-200",
            "badge_cls": "bg-sky-200 text-sky-900"
        },
        {
            "status": "boglandi",
            "title": "Bog'lanildi",
            "icon": "🟢",
            "subtitle": "Muvaffaqiyatli gaplashildi",
            "border": "border-emerald-300",
            "header_bg": "bg-emerald-100 text-emerald-900 border border-emerald-200",
            "badge_cls": "bg-emerald-200 text-emerald-900"
        },
        {
            "status": "zahira",
            "title": "Zahira (Keyingi oqim)",
            "icon": "📦",
            "subtitle": "Yangi ochiladigan kurslar uchun",
            "border": "border-indigo-300",
            "header_bg": "bg-indigo-100 text-indigo-900 border border-indigo-200",
            "badge_cls": "bg-indigo-200 text-indigo-900"
        },
        {
            "status": "rad",
            "title": "Rad / Ko'tarmadi",
            "icon": "🔴",
            "subtitle": "Bog'lanib bo'lmadi",
            "border": "border-rose-300",
            "header_bg": "bg-rose-100 text-rose-900 border border-rose-200",
            "badge_cls": "bg-rose-200 text-rose-900"
        }
    ]

    kanban_columns_html = ""
    for col in columns_meta:
        st_key = col["status"]
        cards_list = kanban_cards_dict.get(st_key, [])
        col_cards_inner = "".join(cards_list) if cards_list else '<div class="empty-col-placeholder py-8 text-center text-xs text-slate-400 font-medium">Hozircha lidlar yo\'q</div>'
        
        kanban_columns_html += f"""
        <div class="kanban-col flex-1 min-w-[285px] sm:min-w-[305px] max-w-[340px] flex flex-col bg-slate-50/70 rounded-2xl border {col['border']} p-2.5 shadow-xs transition"
             data-col-status="{st_key}"
             ondragover="handleDragOver(event)"
             ondragleave="handleDragLeave(event)"
             ondrop="handleDrop(event, '{st_key}')">
            <div class="flex items-center justify-between p-2.5 rounded-xl {col['header_bg']} mb-2.5 shadow-2xs">
                <div>
                    <div class="text-xs font-bold flex items-center gap-1.5">
                        <span>{col['icon']}</span>
                        <span>{col['title']}</span>
                    </div>
                    <div class="text-[10px] opacity-80 font-medium">{col['subtitle']}</div>
                </div>
                <span id="badge_count_{st_key}" class="px-2 py-0.5 rounded-full text-xs font-black {col['badge_cls']}">
                    {len(cards_list)} ta
                </span>
            </div>
            <div class="kanban-cards-box flex-1 space-y-2.5 overflow-y-auto max-h-[70vh] pr-1" id="kanban_col_{st_key}">
                {col_cards_inner}
            </div>
        </div>
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
    operator_username = settings.get("operator_username", "operator")
    operator_password = settings.get("operator_password", "operator123")

    leads_header_action_th = '<th class="px-5 py-3.5 text-right">Boshqarish & Holat</th>'
    if is_operator:
        user_role_badge = f'<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-800 border border-blue-200 shadow-2xs">👤 {curr_display_name} (Operator)</span>'
    elif is_supervisor:
        user_role_badge = f'<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-900 border border-amber-300 shadow-2xs">🛡️ {curr_display_name} (Supervisor / Rahbar)</span>'
    else:
        user_role_badge = f'<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-purple-50 text-purple-800 border border-purple-200 shadow-2xs">👑 {curr_display_name} (Admin)</span>'
    header_stats_btn = '<button onclick="switchTab(\'analytics\')" class="inline-flex items-center gap-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold transition" title="Statistika va Tahlil">📊 Statistika</button>'

    suspicious_nav_badge = f'<span class="bg-rose-100 text-rose-700 text-xs px-2 py-0.5 rounded-full font-bold">{total_suspicious} ta</span>' if total_suspicious > 0 else '<span class="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded-full font-bold">0</span>'

    if is_operator:
        tabs_nav_html = f"""
        <!-- CRM Bo'limlar Navigatsiyasi (Operator rejimi) -->
        <div class="bg-slate-200/80 p-1.5 rounded-2xl flex flex-wrap items-center justify-between gap-2 mb-6 text-sm font-semibold text-slate-600">
            <div class="flex items-center gap-2">
                <button type="button" onclick="switchTab('leads')" id="tab_btn_leads" class="tab-btn active px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                    👥 1. Lidlar Bazasi <span class="bg-purple-100 text-purple-700 text-xs px-2 py-0.5 rounded-full font-bold">{total_leads}</span>
                </button>
                <button type="button" onclick="switchTab('analytics')" id="tab_btn_analytics" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                    📊 2. Statistika & Tahlil
                </button>
            </div>
            <div class="text-xs text-slate-700 font-bold px-3 py-1.5 rounded-xl bg-white border border-slate-200 flex items-center gap-2 shadow-xs">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>👤 Mutaxassis: <b>{curr_display_name}</b></span>
            </div>
        </div>
    """
    elif is_supervisor:
        tabs_nav_html = f"""
        <!-- CRM Bo'limlar Navigatsiyasi (Supervisor / Rahbar rejimi) -->
        <div class="bg-slate-200/80 p-1.5 rounded-2xl flex flex-wrap gap-1.5 mb-6 text-sm font-semibold text-slate-600">
            <button type="button" onclick="switchTab('leads')" id="tab_btn_leads" class="tab-btn active px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                👥 1. Lidlar Bazasi <span class="bg-purple-100 text-purple-700 text-xs px-2 py-0.5 rounded-full font-bold">{total_leads}</span>
            </button>
            <button type="button" onclick="switchTab('analytics')" id="tab_btn_analytics" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                📊 2. Statistika (Kunlik/Oylik/Umumiy)
            </button>
            <button type="button" onclick="switchTab('audit')" id="tab_btn_audit" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                🛡️ 3. Xodimlar Auditi & Nazorat {suspicious_nav_badge}
            </button>
            <button type="button" onclick="switchTab('operators')" id="tab_btn_operators" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                👥 4. Operatorlar <span class="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded-full font-bold">{len(operators)}</span>
            </button>
        </div>
    """
    else:
        tabs_nav_html = f"""
        <!-- CRM Bo'limlar Navigatsiyasi (Admin) -->
        <div class="bg-slate-200/80 p-1.5 rounded-2xl flex flex-wrap gap-1 mb-6 text-sm font-semibold text-slate-600">
            <button type="button" onclick="switchTab('leads')" id="tab_btn_leads" class="tab-btn active px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                👥 1. Lidlar Bazasi <span class="bg-purple-100 text-purple-700 text-xs px-2 py-0.5 rounded-full font-bold">{total_leads}</span>
            </button>
            <button type="button" onclick="switchTab('analytics')" id="tab_btn_analytics" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                📊 2. Statistika & Tahlil
            </button>
            <button type="button" onclick="switchTab('audit')" id="tab_btn_audit" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                🛡️ 3. Xodimlar Auditi {suspicious_nav_badge}
            </button>
            <button type="button" onclick="switchTab('ai')" id="tab_btn_ai" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                🤖 4. Sun'iy Intellekt
            </button>
            <button type="button" onclick="switchTab('campaigns')" id="tab_btn_campaigns" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                🎬 5. Video Qoidalari <span class="bg-slate-100 text-slate-600 text-xs px-2 py-0.5 rounded-full font-bold">{len(campaigns)}</span>
            </button>
            <button type="button" onclick="switchTab('templates')" id="tab_btn_templates" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                💬 6. Direct Shabloni
            </button>
            <button type="button" onclick="switchTab('operators')" id="tab_btn_operators" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                👥 7. Operatorlar <span class="bg-indigo-100 text-indigo-700 text-xs px-2 py-0.5 rounded-full font-bold">{len(operators)}</span>
            </button>
            <button type="button" onclick="switchTab('security')" id="tab_btn_security" class="tab-btn px-4 py-2.5 rounded-xl transition flex items-center gap-2 cursor-pointer">
                🔐 8. Login & Parol
            </button>
        </div>
    """

    # Chart.js JSON ma'lumotlari
    json_daily_labels = json.dumps(daily_labels)
    json_daily_totals = json.dumps(chart_daily_totals)
    json_daily_phones = json.dumps(chart_daily_phones)
    json_top_campaign_labels = json.dumps(top_campaign_labels)
    json_top_campaign_counts = json.dumps(top_campaign_counts)

    if is_operator:
        admin_scripts_js = ""
    else:
        admin_scripts_js = """
        async function checkCurrentToken() {
            const input = document.getElementById('page_access_token_input');
            const box = document.getElementById('token_status_box');
            const tokenVal = input ? input.value.trim() : '';
            if (!box) return;

            box.className = 'text-xs rounded-xl p-3 font-medium bg-blue-50 text-blue-700 border border-blue-200 block';
            box.innerHTML = '⏳ Meta API orqali token holati tekshirilmoqda...';

            try {
                const resp = await fetch('/api/check-token?token=' + encodeURIComponent(tokenVal));
                const data = await resp.json();
                if (data.ok) {
                    box.className = 'text-xs rounded-xl p-3 font-medium bg-emerald-50 text-emerald-800 border border-emerald-200 block';
                    box.innerHTML = '✅ <b>Token 100% Faol!</b> Akkaunt: <b>@' + (data.username || '') + '</b> (' + (data.name || '') + ') | ID: ' + (data.id || '');
                } else {
                    box.className = 'text-xs rounded-xl p-3 font-medium bg-rose-50 text-rose-800 border border-rose-200 block';
                    box.innerHTML = '❌ <b>Token nofaol yoki bloklangan:</b> ' + (data.error || 'Xatolik') + '<br><span class="text-[11px] text-rose-600 mt-1 block">👉 developers.facebook.com dan yangi token olib, shu yerga kiriting va pastdagi &quot;Direct Shabloni Saqlash&quot; tugmasini bosing.</span>';
                }
            } catch (e) {
                box.className = 'text-xs rounded-xl p-3 font-medium bg-rose-50 text-rose-800 border border-rose-200 block';
                box.innerHTML = '⚠️ Server bilan bog\\'lanishda xatolik: ' + e.message;
            }
        }
        """

    analytics_tab_html = f"""
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
                        <button type="button" onclick="exportLeadsToExcel(this)" class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white text-xs font-bold shadow-lg shadow-emerald-500/25 transition cursor-pointer" title="Microsoft Excel (.xlsx) formatida to'liq formatlangan holda yuklab olish">
                            📥 Excel (.XLSX)
                        </button>
                    </div>
                </div>
            </div>

            <!-- Davrlar bo'yicha Tahlil (Bugun, Oylik, Umumiy) -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <!-- Bugungi Tahlil -->
                <div class="p-5 rounded-2xl bg-gradient-to-br from-purple-50 to-indigo-50/50 border border-purple-200/80 shadow-xs">
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-xs font-extrabold uppercase tracking-wider text-purple-700 flex items-center gap-1.5">
                            <span>📅</span> <span>Bugun ({now_date_display})</span>
                        </span>
                        <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-800">Kunlik</span>
                    </div>
                    <div class="text-3xl font-black text-slate-900 mb-2">{today_total} <span class="text-xs text-slate-500 font-normal">ta yangi lid</span></div>
                    <div class="space-y-1.5 text-xs text-slate-600 border-t border-purple-200/60 pt-2.5">
                        <div class="flex justify-between">
                            <span>📞 Olingan telefonlar:</span>
                            <span class="font-bold text-emerald-700">{today_phones} ta</span>
                        </div>
                        <div class="flex justify-between">
                            <span>🟢 Bog'lanildi:</span>
                            <span class="font-bold text-indigo-700">{today_done} ta</span>
                        </div>
                        <div class="flex justify-between">
                            <span>📈 Kunlik konversiya:</span>
                            <span class="font-bold text-purple-700">{today_conv}%</span>
                        </div>
                    </div>
                </div>

                <!-- Shu Oygi Tahlil -->
                <div class="p-5 rounded-2xl bg-gradient-to-br from-indigo-50 to-blue-50/50 border border-indigo-200/80 shadow-xs">
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-xs font-extrabold uppercase tracking-wider text-indigo-700 flex items-center gap-1.5">
                            <span>🗓️</span> <span>Shu Oy ({current_month_name})</span>
                        </span>
                        <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-800">Oylik</span>
                    </div>
                    <div class="text-3xl font-black text-slate-900 mb-2">{month_total} <span class="text-xs text-slate-500 font-normal">ta oylik lid</span></div>
                    <div class="space-y-1.5 text-xs text-slate-600 border-t border-indigo-200/60 pt-2.5">
                        <div class="flex justify-between">
                            <span>📞 Olingan telefonlar:</span>
                            <span class="font-bold text-emerald-700">{month_phones} ta</span>
                        </div>
                        <div class="flex justify-between">
                            <span>🟢 Bog'lanildi:</span>
                            <span class="font-bold text-indigo-700">{month_done} ta</span>
                        </div>
                        <div class="flex justify-between">
                            <span>📈 Oylik konversiya:</span>
                            <span class="font-bold text-indigo-700">{month_conv}%</span>
                        </div>
                    </div>
                </div>

                <!-- Umumiy Tahlil -->
                <div class="p-5 rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50/50 border border-emerald-200/80 shadow-xs">
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-xs font-extrabold uppercase tracking-wider text-emerald-800 flex items-center gap-1.5">
                            <span>🌐</span> <span>Barcha Davr (Umumiy)</span>
                        </span>
                        <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">Umumiy</span>
                    </div>
                    <div class="text-3xl font-black text-slate-900 mb-2">{total_leads} <span class="text-xs text-slate-500 font-normal">ta jami lid</span></div>
                    <div class="space-y-1.5 text-xs text-slate-600 border-t border-emerald-200/60 pt-2.5">
                        <div class="flex justify-between">
                            <span>📞 Telefonli lidlar:</span>
                            <span class="font-bold text-emerald-700">{leads_with_phone} ta ({phone_rate}%)</span>
                        </div>
                        <div class="flex justify-between">
                            <span>🟢 Bog'lanildi:</span>
                            <span class="font-bold text-indigo-700">{done_leads} ta ({conversion_rate}%)</span>
                        </div>
                        <div class="flex justify-between">
                            <span>⚠️ Shubhali holatlar:</span>
                            <span class="font-bold {'text-rose-600' if total_suspicious > 0 else 'text-slate-500'}">{total_suspicious} ta</span>
                        </div>
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
                        <div class="flex items-center justify-between p-1.5 bg-emerald-50 rounded-lg">
                            <span class="flex items-center gap-1 text-emerald-700"><span class="w-2 h-2 rounded-full bg-emerald-500"></span> Bog'lanildi:</span>
                            <span class="font-bold text-emerald-900">{done_leads} ta</span>
                        </div>
                        <div class="flex items-center justify-between p-1.5 bg-amber-50 rounded-lg">
                            <span class="flex items-center gap-1 text-amber-700"><span class="w-2 h-2 rounded-full bg-amber-500"></span> O'ylayapti:</span>
                            <span class="font-bold text-amber-900">{thinking_leads} ta</span>
                        </div>
                        <div class="flex items-center justify-between p-1.5 bg-indigo-50 rounded-lg">
                            <span class="flex items-center gap-1 text-indigo-700"><span class="w-2 h-2 rounded-full bg-indigo-500"></span> Zahira:</span>
                            <span class="font-bold text-indigo-900">{reserve_leads} ta</span>
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
                                <th class="px-4 py-3 text-center">💭 O'ylayapti</th>
                                <th class="px-4 py-3 text-center">🟢 Bog'lanildi</th>
                                <th class="px-4 py-3 text-center">📦 Zahira</th>
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
    """

    # ---------------- 5.5 ANTI-FRAUD VA AUDIT JURNALI TAHLILI ----------------
    audit_managers_rows = ""
    for m in sorted_managers:
        m_name = m["name"]
        m_total = m["total"]
        m_today = m["today"]
        m_month = m["month"]
        m_done = m["boglandi"]
        m_phone = m["phones"]
        m_direct = m["direct_msgs"]
        m_susp = m["suspicious"]

        if m_name == "Biriktirilmagan (Yangi)":
            m_avatar = "⚪"
            m_label = f'<span class="font-medium text-slate-500 italic">{m_name}</span>'
        else:
            m_avatar = "👤"
            m_label = f'<span class="font-bold text-slate-800">{m_name}</span>'

        if m_susp > 0:
            susp_badge = f'<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300 animate-pulse">⚠️ {m_susp} ta shubhali</span>'
            status_eval = '<span class="text-xs text-rose-600 font-semibold">Tekshirish lozim</span>'
        else:
            susp_badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">✅ Toza</span>'
            status_eval = '<span class="text-xs text-emerald-600 font-semibold">Qoidaga muvofiq</span>'

        audit_managers_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50/70 transition">
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-2.5">
                    <span class="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center text-sm font-bold border border-indigo-100">{m_avatar}</span>
                    {m_label}
                </div>
            </td>
            <td class="px-4 py-3.5 text-center font-bold text-slate-800">{m_today}</td>
            <td class="px-4 py-3.5 text-center font-bold text-slate-800">{m_month}</td>
            <td class="px-4 py-3.5 text-center font-bold text-slate-900">{m_total}</td>
            <td class="px-4 py-3.5 text-center font-semibold text-emerald-700">{m_phone}</td>
            <td class="px-4 py-3.5 text-center font-semibold text-pink-700">{m_direct}</td>
            <td class="px-4 py-3.5 text-center font-bold text-slate-800">{m_done}</td>
            <td class="px-4 py-3.5 text-center">{susp_badge}</td>
            <td class="px-5 py-3.5 text-right whitespace-nowrap">{status_eval}</td>
        </tr>
        """

    # Activity Logs table rows
    activity_rows_html = ""
    if not activity_logs:
        activity_rows_html = """
        <tr>
            <td colspan="5" class="px-6 py-8 text-center text-slate-400">
                Hozircha xodimlarning harakatlar jurnali mavjud emas. Mutaxassislar lidlar holatini o'zgartirganda, izoh yozganda yoki xabar yuborganda bu yerda avtomatik qayd etiladi.
            </td>
        </tr>
        """
    else:
        for log in activity_logs:
            l_time = log.get("created_at") or "—"
            l_op = log.get("operator_name") or "Tizim"
            l_type = log.get("action_type") or "harakat"
            l_cid = log.get("client_id") or "—"
            l_det = log.get("details") or "—"

            if l_type == "status":
                type_badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold bg-purple-50 text-purple-700 border border-purple-200">🔄 Holat</span>'
            elif l_type == "comment":
                type_badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">📝 Izoh</span>'
            elif l_type == "direct_message":
                type_badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold bg-pink-50 text-pink-700 border border-pink-200">💬 Direct</span>'
            else:
                type_badge = f'<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold bg-slate-100 text-slate-700">{l_type}</span>'

            activity_rows_html += f"""
            <tr class="border-b border-slate-100 hover:bg-slate-50/70 transition">
                <td class="px-5 py-3 text-xs font-mono text-slate-500 whitespace-nowrap">{l_time}</td>
                <td class="px-4 py-3 whitespace-nowrap font-bold text-slate-800 text-xs">👤 {l_op}</td>
                <td class="px-4 py-3 text-center whitespace-nowrap">{type_badge}</td>
                <td class="px-4 py-3 text-center whitespace-nowrap text-xs font-mono text-purple-700 font-bold">#{l_cid}</td>
                <td class="px-5 py-3 text-xs text-slate-700">{l_det}</td>
            </tr>
            """

    if is_operator:
        audit_tab_html = ""
    else:
        if total_suspicious > 0:
            anti_fraud_banner = f"""
            <div class="p-6 rounded-3xl bg-gradient-to-r from-rose-600 via-rose-700 to-red-800 text-white shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div class="flex items-start gap-3.5">
                    <span class="text-3xl">⚠️</span>
                    <div>
                        <h3 class="text-lg font-extrabold">Diqqat: Tizimda {total_suspicious} ta shubhali holat aniqlandi!</h3>
                        <p class="text-rose-100 text-xs sm:text-sm mt-1 max-w-2xl">
                            Ushbu lidlar bo'yicha mijoz bilan telefon orqali gaplashilmagan (telefon raqami yo'q) va Instagram Direct orqali ham xabar yuborilmagan, biroq xodimlar tomonidan &quot;🟢 Bog'lanildi&quot; deb belgilangan.
                        </p>
                    </div>
                </div>
                <button type="button" onclick="filterSuspiciousLeads()" class="px-4 py-2.5 bg-white text-rose-800 hover:bg-rose-50 rounded-xl text-xs sm:text-sm font-extrabold shadow-md transition whitespace-nowrap cursor-pointer">
                    🔍 Shubhali lidlarni ochish ({total_suspicious} ta)
                </button>
            </div>
            """
        else:
            anti_fraud_banner = f"""
            <div class="p-6 rounded-3xl bg-gradient-to-r from-emerald-700 to-teal-800 text-white shadow-lg flex items-center justify-between gap-4">
                <div class="flex items-center gap-3.5">
                    <span class="text-3xl">🛡️</span>
                    <div>
                        <h3 class="text-lg font-extrabold">Anti-Fraud Nazorati Faol: Barcha Bog'lanishlar Toza</h3>
                        <p class="text-emerald-100 text-xs sm:text-sm mt-1">
                            Hozircha birorta ham soxta yoki asossiz bog'lanish holati aniqlanmadi. Barcha xodimlar qoidalarga to'liq rioya qilmoqda.
                        </p>
                    </div>
                </div>
                <span class="px-3 py-1.5 rounded-xl bg-white/20 text-white text-xs font-bold border border-white/20">
                    100% Tasdiqlangan
                </span>
            </div>
            """

        audit_tab_html = f"""
        <!-- 3-TAB: XODIMLAR AUDITI VA ANTI-FRAUD NAZORATI -->
        <div id="tab_audit" class="tab-content hidden space-y-6">
            {anti_fraud_banner}

            <!-- Mutaxassislar Faoliyati va Nazorat Jadvali -->
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-100">
                    <div>
                        <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                            <span>🛡️</span> <span>Mutaxassislarning Haqiqiy Ish Unumdorligi va Nazorati</span>
                        </h3>
                        <p class="text-xs text-slate-500 mt-0.5">Telefon olish, Direct orqali yozishish va shubhali holatlar balansi</p>
                    </div>
                    <span class="text-xs font-bold text-slate-600 bg-slate-100 px-3 py-1.5 rounded-xl">
                        Kuzatuv ostida: {len(operators)} ta mutaxassis
                    </span>
                </div>
                <div class="overflow-x-auto rounded-xl border border-slate-100">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 border-b border-slate-100 tracking-wider">
                            <tr>
                                <th class="px-5 py-3">Mutaxassis</th>
                                <th class="px-4 py-3 text-center">Bugungi Lidlar</th>
                                <th class="px-4 py-3 text-center">Oylik Lidlar</th>
                                <th class="px-4 py-3 text-center">Jami Biriktirilgan</th>
                                <th class="px-4 py-3 text-center">📞 Olingan Telefonlar</th>
                                <th class="px-4 py-3 text-center">💬 Direct Xabarlar</th>
                                <th class="px-4 py-3 text-center">🟢 Bog'landi Belgilangan</th>
                                <th class="px-4 py-3 text-center">⚠️ Shubhali Holat</th>
                                <th class="px-5 py-3 text-right">Audit Xulosasi</th>
                            </tr>
                        </thead>
                        <tbody>
                            {audit_managers_rows}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Jonli Harakatlar Jurnali (Audit Activity Log) -->
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 sm:p-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-100">
                    <div>
                        <h3 class="font-extrabold text-slate-900 text-base flex items-center gap-2">
                            <span>📜</span> <span>Xodimlarning Jonli Harakatlar Jurnali (Audit Log)</span>
                        </h3>
                        <p class="text-xs text-slate-500 mt-0.5">Kim, qachon, qaysi mijozning statusini o'zgartirdi, izoh yozdi yoki xabar jo'natdi</p>
                    </div>
                    <button onclick="window.location.reload()" class="text-xs text-purple-700 bg-purple-50 hover:bg-purple-100 px-3 py-1.5 rounded-xl font-bold transition">
                        🔄 Yangilash
                    </button>
                </div>
                <div class="overflow-x-auto rounded-xl border border-slate-100 max-h-96">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-50 text-[11px] font-bold uppercase text-slate-500 border-b border-slate-100 tracking-wider sticky top-0 bg-slate-50">
                            <tr>
                                <th class="px-5 py-3">Vaqti</th>
                                <th class="px-4 py-3">Xodim</th>
                                <th class="px-4 py-3 text-center">Amal Turi</th>
                                <th class="px-4 py-3 text-center">Mijoz ID</th>
                                <th class="px-5 py-3">Tafsilotlar</th>
                            </tr>
                        </thead>
                        <tbody>
                            {activity_rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """

    # Operatorlar HTML jadvali
    operators_table_rows = ""
    if not operators:
        operators_table_rows = """
        <tr>
            <td colspan="7" class="px-6 py-8 text-center text-slate-400">
                Hozircha qo'shimcha operatorlar qo'shilmagan.
            </td>
        </tr>
        """
    for op in operators:
        op_id = op.get("id")
        op_name = op.get("display_name") or op.get("username")
        op_user = op.get("username")
        op_phone = op.get("phone") or "—"
        op_active = op.get("is_active", 1)
        op_last = op.get("last_login") or "Kirilmagan"
        op_leads_cnt = op_lead_counts.get(op_name, 0)
        op_allowed = (op.get("allowed_directions") or "all").strip()

        escaped_op_name = str(op_name).replace("'", "\\'")

        # Yo'nalishlar nishonlari (badges)
        if op_allowed == "all" or not op_allowed:
            allowed_badges_html = '<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200 shadow-2xs">🌐 Barcha yo\'nalishlar</span>'
        else:
            badges = []
            for k in op_allowed.split(","):
                k = k.strip()
                if k in dir_dict:
                    badges.append(f'<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-50 text-purple-700 border border-purple-200 whitespace-nowrap shadow-2xs">{dir_dict[k]["short"]}</span>')
            allowed_badges_html = f'<div class="flex flex-wrap gap-1 max-w-[240px]">{"".join(badges)}</div>' if badges else '<span class="text-xs text-slate-400 italic">Belgilanmagan</span>'

        status_pill = '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">🟢 Faol</span>' if op_active else '<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">🔴 Bloklangan</span>'
        toggle_label = "Bloklash" if op_active else "Faollashtirish"
        toggle_btn_class = "text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200" if op_active else "text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200"

        operators_table_rows += f"""
        <tr class="border-b border-slate-100 hover:bg-slate-50/70 transition">
            <td class="px-5 py-3.5 whitespace-nowrap">
                <div class="flex items-center gap-2.5">
                    <div class="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center text-sm font-bold border border-indigo-100 shadow-2xs">👤</div>
                    <div>
                        <div class="font-bold text-slate-900">{op_name}</div>
                        <div class="text-xs text-slate-500 font-mono">@{op_user}</div>
                    </div>
                </div>
            </td>
            <td class="px-4 py-3.5 text-xs font-medium text-slate-700 whitespace-nowrap">{op_phone}</td>
            <td class="px-4 py-3.5" id="op_dirs_td_{op_id}">{allowed_badges_html}</td>
            <td class="px-4 py-3.5 text-center whitespace-nowrap">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-50 text-purple-700 border border-purple-200">{op_leads_cnt} ta lid</span>
            </td>
            <td class="px-4 py-3.5 text-center whitespace-nowrap">{status_pill}</td>
            <td class="px-4 py-3.5 text-xs text-slate-500 whitespace-nowrap">{op_last}</td>
            <td class="px-5 py-3.5 text-right whitespace-nowrap">
                <div class="inline-flex items-center gap-1.5">
                    <button type="button" onclick="openDirectionsModal('{op_id}', '{escaped_op_name}', '{op_allowed}')" class="text-xs px-2.5 py-1 rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold transition cursor-pointer" title="Yo'nalishlarni biriktirish">🎯 Yo'nalishlar</button>
                    <button type="button" onclick="openPasswordChangeModal('{op_id}', '{escaped_op_name}', '{op_user}')" class="text-xs px-2.5 py-1 rounded-lg bg-purple-50 hover:bg-purple-100 text-purple-700 border border-purple-200 font-medium transition cursor-pointer" title="Parolni o'zgartirish">🔑 Parol</button>
                    <form method="POST" action="/admin/operators/{op_id}/toggle-status" class="inline">
                        <button type="submit" class="text-xs px-2.5 py-1 rounded-lg {toggle_btn_class} font-medium transition cursor-pointer">{toggle_label}</button>
                    </form>
                    <form method="POST" action="/admin/operators/{op_id}/delete" onsubmit="return confirm('Haqiqatan ham {escaped_op_name} operatorini o\\'chirmoqchimisiz?')" class="inline">
                        <button type="submit" class="text-xs px-2 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 font-medium transition cursor-pointer" title="O'chirish">🗑️</button>
                    </form>
                </div>
            </td>
        </tr>
        """

    op_table_col_class = "lg:col-span-2" if is_admin else "lg:col-span-3"
    new_op_form_html = f"""
    <div class="lg:col-span-1 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div class="flex items-center gap-2 mb-3">
            <span class="text-2xl">➕</span>
            <div>
                <h3 class="text-base font-bold text-slate-800">Yangi Operator Qo'shish</h3>
                <p class="text-xs text-slate-400">Mutaxassisga login va parol berish</p>
            </div>
        </div>
        <form method="POST" action="/admin/operators/create" class="space-y-4">
            <div>
                <label class="block text-xs font-bold text-slate-700 mb-1">Ism va Familiya *</label>
                <input type="text" name="display_name" required placeholder="Masalan: Aziza Karimova" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 outline-none">
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-700 mb-1">Login (Username) *</label>
                <input type="text" name="username" required placeholder="Masalan: aziza" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-mono focus:ring-2 focus:ring-purple-500 outline-none">
                <p class="text-[11px] text-slate-400 mt-0.5">Kichik lotin harflarida, probellarsiz</p>
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-700 mb-1">Parol *</label>
                <input type="text" name="password" required placeholder="Masalan: aziza2026" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 outline-none">
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-700 mb-1">Telefon raqami (ixtiyoriy)</label>
                <input type="text" name="phone" placeholder="+998901234567" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-mono focus:ring-2 focus:ring-purple-500 outline-none">
            </div>
            <div>
                <label class="block text-xs font-bold text-slate-700 mb-1">Mas'ul Yo'nalishlar</label>
                <div class="space-y-1 p-2 bg-slate-50 rounded-xl border border-slate-200 text-xs max-h-36 overflow-y-auto">
                    <label class="flex items-center gap-2 p-1 hover:bg-white rounded cursor-pointer font-bold text-purple-700">
                        <input type="checkbox" name="directions" value="all" checked id="newOpAllDirsCheck" onchange="toggleNewOpDirs(this)">
                        <span>🌐 Barchasi (Cheklanmagan)</span>
                    </label>
                    {new_op_dir_checkboxes}
                </div>
                <p class="text-[11px] text-slate-400 mt-0.5">Xodimga faqat belgilangan yo'nalishdagi lidlar ko'rinadi</p>
            </div>
            <button type="submit" class="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-xs shadow-md shadow-purple-500/20 transition cursor-pointer">
                ➕ Operatorni Saqlash
            </button>
        </form>
    </div>
    """ if is_admin else ""

    if is_operator:
        operators_tab_html = ""
    else:
        operators_tab_html = f"""
        <!-- 4-TAB: OPERATORLAR VA MUTAXASSISLAR BOSHQARUVI -->
        <div id="tab_operators" class="tab-content hidden space-y-6">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {new_op_form_html}

                <!-- Operatorlar Ro'yxati Table -->
                <div class="{op_table_col_class} bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
                        <div class="flex items-center gap-2">
                            <span class="text-2xl">👥</span>
                            <div>
                                <h3 class="text-base font-bold text-slate-800">Mavjud Mutaxassislar (Operatorlar)</h3>
                                <p class="text-xs text-slate-500">Har bir xodim o'z login/paroli bilan kirib lidlar bilan ishlaydi</p>
                            </div>
                        </div>
                        <span class="text-xs font-bold text-purple-700 bg-purple-50 px-3 py-1.5 rounded-xl border border-purple-200">Jami: {len(operators)} ta xodim</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left border-collapse text-sm">
                            <thead>
                                <tr class="border-b border-slate-200 text-xs font-bold text-slate-500 bg-slate-50/70">
                                    <th class="px-5 py-3">Xodim</th>
                                    <th class="px-4 py-3">Telefon</th>
                                    <th class="px-4 py-3">🎯 Biriktirilgan Yo'nalishlar</th>
                                    <th class="px-4 py-3 text-center">Lidlari</th>
                                    <th class="px-4 py-3 text-center">Holati</th>
                                    <th class="px-4 py-3">Oxirgi kirishi</th>
                                    <th class="px-5 py-3 text-right">Amallar</th>
                                </tr>
                            </thead>
                            <tbody>
                                {operators_table_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        """

    if not is_admin:
        admin_only_tabs_html = ""
    else:
        admin_only_tabs_html = f"""
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

        <!-- 8-TAB: XAVFSIZLIK & LOGIN PAROL -->
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
                            💾 Admin Login va Parolni Yangilash
                        </button>
                    </div>
                </form>
            </div>

            <!-- Operator Akkaunti (Cheklangan Ruxsat) -->
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 max-w-2xl mt-6">
                <div class="border-b border-slate-100 pb-4 mb-6">
                    <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                        👥 Operator Akkaunti (Sotuv Bo'limi & Lidlar bilan Ishlash)
                    </h2>
                    <p class="text-sm text-slate-500">
                        Ushbu login va parol operatorlar / sotuv bo'limi uchun. Ular tizimga kirganda lidlar bilan to'g'ridan-to'g'ri bog'lanish (qo'ng'iroq, Telegram, Instagram), ularning holatini (statusini) o'zgartirish va izoh yozish imkoniyatiga ega bo'ladi. Tizim sozlamalari va lidlarni o'chirish faqat Admin uchun saqlanadi.
                    </p>
                </div>

                <form method="POST" action="/admin/security/operator/save" class="space-y-5">
                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1.5">Operator Logini:</label>
                        <input type="text" name="operator_username" required value="{operator_username}" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm font-medium focus:ring-2 focus:ring-purple-500 outline-none">
                    </div>

                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1.5">Operator Paroli:</label>
                        <input type="text" name="operator_password" required value="{operator_password}" placeholder="Kamida 4 ta belgi" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 outline-none">
                        <p class="text-xs text-slate-400 mt-1">Parolni bu yerdan istalgan vaqt yangilab, operatorga berishingiz mumkin.</p>
                    </div>

                    <div class="pt-2">
                        <button type="submit" class="bg-purple-600 hover:bg-purple-700 text-white font-bold px-6 py-2.5 rounded-xl text-sm shadow-sm transition">
                            💾 Operator Login va Parolini Saqlash
                        </button>
                    </div>
                </form>
            </div>
        </div>
    """

    common_modals_html = f"""
    <!-- Instagram Direct Suhbat Modali -->
    <div id="instagramChatModal" class="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-3 sm:p-4 hidden">
        <div class="bg-white rounded-2xl max-w-2xl w-full h-[88vh] max-h-[720px] shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
            <!-- Modal Header -->
            <div class="px-5 py-3.5 bg-white border-b border-slate-100 flex items-center justify-between shrink-0">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600 text-white flex items-center justify-center text-lg shadow-sm">
                        📸
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <h3 class="text-sm font-bold text-slate-900" id="chatModalClientName">Mijoz Ismi</h3>
                            <a id="chatModalUsername" href="#" target="_blank" class="text-xs font-bold text-pink-600 hover:text-pink-700 hover:underline font-mono" title="Instagramda ochish">@username</a>
                        </div>
                        <div class="flex items-center gap-2 mt-0.5">
                            <span id="chatModalCourseBadge" class="text-[11px] font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-md border border-purple-200">Yo'nalish: Front Office</span>
                            <span id="chatModalAiBadge" class="text-[11px] font-bold px-2 py-0.5 rounded-md">⚡ AI Faol</span>
                        </div>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <a id="chatModalOpenIgBtn" href="#" target="_blank" class="text-xs font-bold px-3 py-1.5 rounded-xl bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white shadow-xs transition flex items-center gap-1 cursor-pointer" title="Ushbu mijozni to'g'ridan-to'g'ri Instagram ilovasida ochish">
                        <span>📸 Instagram</span>
                    </a>
                    <button type="button" id="chatModalToggleAiBtn" onclick="toggleClientAi()" class="text-xs font-bold px-3 py-1.5 rounded-xl border transition flex items-center gap-1.5 cursor-pointer shadow-xs" title="AI javoblarini to'xtatish yoki qayta yoqish">
                        <!-- JS orqali to'ldiriladi -->
                    </button>
                    <button type="button" onclick="closeChatModal()" class="text-slate-400 hover:text-slate-600 text-2xl font-bold leading-none p-1.5 rounded-lg hover:bg-slate-100 transition cursor-pointer">&times;</button>
                </div>
            </div>

            <!-- AI Ogohlantirish Paneli -->
            <div id="chatModalAiNotice" class="px-5 py-2 bg-amber-50 border-b border-amber-200/80 text-[11px] text-amber-900 flex items-center justify-between hidden">
                <div class="flex items-center gap-1.5">
                    <span>🛑</span>
                    <span><b>AI To'xtatilgan:</b> Ushbu mijozga sun'iy intellekt avtomatik javob bermaydi. Barcha xabarlarga faqat mutaxassis javob beradi.</span>
                </div>
                <button type="button" onclick="toggleClientAi()" class="text-[11px] font-bold text-purple-700 underline hover:text-purple-900 ml-2 whitespace-nowrap cursor-pointer">AI ni yoqish</button>
            </div>

            <!-- Xabarlar Tarixi Box (Scrollable) -->
            <div id="chatMessagesBox" class="flex-1 p-4 sm:p-5 overflow-y-auto space-y-3 bg-slate-50/70">
                <!-- Xabarlar yuklanmoqda spinner -->
                <div class="flex flex-col items-center justify-center h-full text-slate-400 py-12">
                    <div class="w-8 h-8 border-3 border-purple-600 border-t-transparent rounded-full animate-spin mb-3"></div>
                    <span class="text-xs font-medium">Suhbat tarixi yuklanmoqda...</span>
                </div>
            </div>

            <!-- Tezkor Javob Shabonlari -->
            <div class="px-4 py-1.5 bg-slate-100/80 border-t border-slate-200/60 flex items-center gap-1.5 overflow-x-auto text-[11px] text-slate-600 shrink-0">
                <span class="font-bold text-slate-400 shrink-0">⚡ Shablonlar:</span>
                <button type="button" onclick="insertQuickReply('Assalomu alaykum! Kursimiz haqida batafsil ma\\'lumot berishimni xohlaysizmi?')" class="px-2.5 py-1 bg-white hover:bg-slate-200 border border-slate-200 rounded-lg whitespace-nowrap text-slate-700 transition cursor-pointer shadow-2xs">👋 Salom & Ma'lumot</button>
                <button type="button" onclick="insertQuickReply('Telefon raqamingizni qoldirsangiz, mutaxassisimiz sizga qo\\'ng\\'iroq qilib barcha savollaringizga javob beradi.')" class="px-2.5 py-1 bg-white hover:bg-slate-200 border border-slate-200 rounded-lg whitespace-nowrap text-slate-700 transition cursor-pointer shadow-2xs">📞 Raqam so'rash</button>
                <button type="button" onclick="insertQuickReply('Sizga qaysi vaqtda qo\\'ng\\'iroq qilsak qulay bo\\'ladi?')" class="px-2.5 py-1 bg-white hover:bg-slate-200 border border-slate-200 rounded-lg whitespace-nowrap text-slate-700 transition cursor-pointer shadow-2xs">⏰ Qulay vaqt</button>
                <button type="button" onclick="insertQuickReply('Darslarimiz amaliyotga asoslangan bo\\'lib, kurs yakunida xalqaro sertifikat beriladi.')" class="px-2.5 py-1 bg-white hover:bg-slate-200 border border-slate-200 rounded-lg whitespace-nowrap text-slate-700 transition cursor-pointer shadow-2xs">🎓 Sertifikat</button>
            </div>

            <!-- Xabar Yuborish Formasi (Footer) -->
            <form id="chatSendForm" onsubmit="sendDirectMessage(event)" class="p-3.5 bg-white border-t border-slate-200 shrink-0">
                <div class="flex items-center gap-2">
                    <input type="text" id="chatInputText" autocomplete="off" placeholder="Mijozga Instagram Direct orqali xabar yozing..." class="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none placeholder-slate-400">
                    <button type="submit" id="chatSendBtn" class="px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white shadow-md shadow-purple-500/20 transition flex items-center gap-1.5 cursor-pointer shrink-0 disabled:opacity-50">
                        <span>Yuborish</span> <span>🚀</span>
                    </button>
                </div>
                <div class="flex items-center justify-between text-[11px] text-slate-400 mt-1.5 px-1">
                    <span>💡 Xabar yuborilgan zahoti <b>AI avtomatik to'xtatiladi</b> (inson nazorati faollashadi).</span>
                    <span class="hidden sm:inline">Enter bosish orqali yuborish</span>
                </div>
            </form>
        </div>
    </div>

    <!-- Bog'lanish & Mutaxassis Izohi Modali -->
    <div id="commentModal" class="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <div class="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
                <div class="flex items-center gap-2.5">
                    <div class="w-10 h-10 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center text-xl font-bold shadow-xs">
                        📞
                    </div>
                    <div>
                        <h3 class="text-base font-bold text-slate-900" id="modalClientTitle">Mijoz bilan Bog'lanish & Izoh</h3>
                        <p class="text-xs text-slate-500 font-medium" id="modalClientCourse">Qiziqqan yo'nalishi: —</p>
                    </div>
                </div>
                <button type="button" onclick="closeCommentModal()" class="text-slate-400 hover:text-slate-600 text-2xl font-bold leading-none p-1.5 rounded-lg hover:bg-slate-100 transition">&times;</button>
            </div>

            <!-- Tezkor Aloqa Tugmalari -->
            <div class="mb-4 p-3.5 bg-slate-50/90 rounded-xl border border-slate-200">
                <div class="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2">⚡ Tezkor Bog'lanish:</div>
                <div class="flex flex-wrap items-center gap-2" id="modalContactButtons">
                    <!-- Dinamik ravishda JS orqali to'ldiriladi: Tel, Telegram, Instagram -->
                </div>
            </div>

            <form method="POST" id="modalCommentForm" action="" onsubmit="saveCommentModal(event)" class="space-y-4">
                <!-- Telefon raqam (kiritish yoki to'g'rilash) -->
                <div>
                    <label class="block text-xs font-bold text-slate-700 mb-1">📞 Telefon Raqami:</label>
                    <input type="text" name="phone" id="modalPhoneInput" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-mono focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none placeholder-slate-400" placeholder="+998901234567">
                    <p class="text-[11px] text-slate-400 mt-1">Agar mijoz raqamini Directda aytgan bo'lsa, shu yerga yozib saqlashingiz mumkin.</p>
                </div>

                <!-- Holatni tanlash -->
                <div>
                    <label class="block text-xs font-bold text-slate-700 mb-1">🎯 Mijoz Holati (Status):</label>
                    <select name="status" id="modalStatusSelect" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none bg-white">
                        <option value="yangi">⚪ Yangi (Bog'lanish kutilmoqda ⏳)</option>
                        <option value="oylanyapti">💭 O'ylayapti (Qaror qabul qilmoqda 🤔)</option>
                        <option value="boglandi">🟢 Bog'lanildi (Muvaffaqiyatli gaplashildi ✅)</option>
                        <option value="zahira">📦 Zahira (Keyingi oqim / ochiladigan kurslar uchun 📦)</option>
                        <option value="rad">🔴 Rad / Ko'tarmadi (Bog'lanib bo'lmadi ❌)</option>
                    </select>
                </div>

                <!-- Mas'ul mutaxassisni tanlash va O'zimga biriktirish -->
                <div>
                    <div class="flex items-center justify-between mb-1">
                        <label class="block text-xs font-bold text-slate-700">👤 Mas'ul Mutaxassis (Operator):</label>
                        <button type="button" onclick="assignToMe('{curr_display_name}')" class="text-[11px] font-bold text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 px-2 py-0.5 rounded-md transition shadow-2xs">⭐ O'zimga biriktirish</button>
                    </div>
                    <select name="manager_name" id="modalManagerSelect" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none bg-white">
                        <option value="">⚪ Biriktirilmagan (Yangi)</option>
                        {operators_options_html}
                    </select>
                </div>

                <!-- Mutaxassis izohi -->
                <div>
                    <label class="block text-xs font-bold text-slate-700 mb-1">📝 Mutaxassis Izohi:</label>
                    <textarea name="comment" id="modalCommentInput" rows="3" class="w-full p-3 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 outline-none placeholder-slate-400 leading-relaxed" placeholder="Mijoz bilan nima gaplashildi, qaysi guruhga yo'naltirildi yoki qachon qayta qo'ng'iroq qilish kerak..."></textarea>
                </div>

                <div class="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-100">
                    <button type="button" onclick="closeCommentModal()" class="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 border border-slate-200 transition">Bekor qilish</button>
                    <button type="submit" class="px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white shadow-md shadow-purple-500/20 transition flex items-center gap-1.5 cursor-pointer">
                        <span>💾</span> <span>Saqlash & Telegramga uzatish</span>
                    </button>
                </div>
            </form>
        </div>
    </div>

    <!-- Operator Parolini Yangilash Modali -->
    <div id="opPasswordModal" class="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200">
            <h3 class="text-base font-bold text-slate-900 mb-1" id="opPasswordTitle">Operator Parolini Yangilash</h3>
            <p class="text-xs text-slate-500 mb-4" id="opPasswordSubtitle">Yangi parol kiriting</p>
            <form method="POST" id="opPasswordForm" action="" onsubmit="saveOpPasswordModal(event)" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-slate-700 mb-1">Yangi Parol:</label>
                    <input type="text" name="new_password" required placeholder="Kamida 4 ta belgi" class="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:ring-2 focus:ring-purple-500 outline-none">
                </div>
                <div class="flex items-center justify-end gap-2 pt-2">
                    <button type="button" onclick="closeOpPasswordModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 border border-slate-200 transition cursor-pointer">Bekor qilish</button>
                    <button type="submit" class="px-4 py-2 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-700 text-white shadow-sm transition cursor-pointer">Saqlash</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Mutaxassis Yo'nalishlarini Belgilash Modali -->
    <div id="directionsModal" class="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 hidden">
        <div class="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in duration-150">
            <div class="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                <div class="flex items-center gap-2.5">
                    <span class="text-2xl">🎯</span>
                    <div>
                        <h3 class="text-base font-extrabold text-slate-900" id="dirsModalTitle">Mutaxassis Yo'nalishlari</h3>
                        <p class="text-xs text-slate-500" id="dirsModalSubtitle">Xodimga faqat tanlangan yo'nalishdagi lidlar ko'rinadi</p>
                    </div>
                </div>
                <button type="button" onclick="closeDirectionsModal()" class="w-8 h-8 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 flex items-center justify-center text-sm font-bold transition cursor-pointer">&times;</button>
            </div>
            <form method="POST" id="dirsForm" action="" onsubmit="saveDirectionsModal(event)" class="space-y-4">
                <div class="flex items-center justify-between text-xs pb-1">
                    <span class="font-bold text-slate-700">Ruxsat etilgan kurslar:</span>
                    <div class="flex items-center gap-2">
                        <button type="button" onclick="toggleAllModalDirections(true)" class="text-purple-600 hover:underline font-bold cursor-pointer">Barchasini belgilash</button>
                        <span class="text-slate-300">|</span>
                        <button type="button" onclick="toggleAllModalDirections(false)" class="text-slate-500 hover:underline font-bold cursor-pointer">Tozalash</button>
                    </div>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-[340px] overflow-y-auto p-2 border border-slate-200/80 rounded-2xl bg-slate-50/50">
                    {modal_dir_checkboxes}
                </div>
                <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                    <button type="button" onclick="closeDirectionsModal()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100 border border-slate-200 transition cursor-pointer">Bekor qilish</button>
                    <button type="submit" class="px-5 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white shadow-md shadow-purple-500/20 transition cursor-pointer">💾 Saqlash</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Toast Xabarnoma -->
    <div id="toastNotification" class="fixed bottom-6 right-6 z-50 transform translate-y-24 opacity-0 transition-all duration-300 pointer-events-none">
        <div class="bg-slate-900/95 text-white text-xs font-semibold px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2.5 border border-slate-700/60 backdrop-blur-sm" id="toastMessage">
            Xabar
        </div>
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram CRM — Xalqaro Turizm Akademiyasi</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js"></script>
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
                        {user_role_badge}
                    </div>
                    <p class="text-xs text-slate-500 font-medium">Xalqaro Turizm Akademiyasi (Samarqand kampusi) — Lidlar va Muloqot Boshqaruvi</p>
                </div>
            </div>
            <div class="flex items-center gap-2.5">
                {header_stats_btn}
                <button type="button" onclick="exportLeadsToExcel(this)" class="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 rounded-xl text-xs sm:text-sm font-semibold shadow-sm transition cursor-pointer" title="Microsoft Excel (.xlsx) formatida yuklab olish">
                    📥 Excel (.XLSX)
                </button>
                <button type="button" onclick="exportLeadsToCSV(this)" class="inline-flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-xl text-xs sm:text-sm font-medium border border-slate-200 transition cursor-pointer" title="CSV formatida yuklab olish">
                    📄 CSV
                </button>
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

        {tabs_nav_html}

        <!-- 1-TAB: LIDLAR BAZASI (CRM) -->
        <div id="tab_leads" class="tab-content space-y-6">
            <!-- Statistika kartalari -->
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
                <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">Jami Lidlar</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-slate-900">{total_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">⚪ Yangi Lidlar</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-slate-700">{new_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-sky-600 mb-1">💭 O'ylayapti</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-sky-600">{thinking_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-emerald-600 mb-1">🟢 Bog'lanildi</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-emerald-600">{done_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-indigo-600 mb-1">📦 Zahira</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-indigo-600">{reserve_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
                <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-bold uppercase tracking-wider text-rose-600 mb-1">🔴 Rad etildi</div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-rose-600">{rejected_leads} <span class="text-xs text-slate-400 font-normal">ta</span></div>
                </div>
            </div>

            {operator_directions_banner}

            <!-- Qidiruv va Filtrlash Paneli -->
            <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-4 sm:p-6">
                <!-- Ko'rinishni tanlash (Ustunlar vs Jadval) -->
                <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-3 mb-4 border-b border-slate-100">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Ko'rinish:</span>
                        <div class="inline-flex p-1 bg-slate-100 rounded-xl border border-slate-200">
                            <button type="button" id="view_btn_kanban" onclick="setViewMode('kanban')" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition bg-white text-purple-700 shadow-xs cursor-pointer">
                                📊 Ustunlar (Pipeline)
                            </button>
                            <button type="button" id="view_btn_table" onclick="setViewMode('table')" class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition text-slate-600 hover:text-slate-900 cursor-pointer">
                                📋 Jadval
                            </button>
                        </div>
                    </div>
                    <div class="text-xs text-slate-500 font-medium flex items-center gap-1.5">
                        <span>💡</span>
                        <span>Lidlarni bosqichlar bo'yicha sudrab (Drag & Drop) yoki tezkor holat menyusi orqali boshqaring</span>
                    </div>
                </div>

                <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4 mb-4">
                    <div class="flex-1 relative">
                        <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">🔍</span>
                        <input type="text" id="lead_search" onkeyup="filterLeads()" placeholder="Ism, telefon yoki kurs bo'yicha qidirish..."
                            class="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 bg-slate-50 focus:bg-white transition">
                    </div>
                    <div class="flex flex-wrap items-center gap-2 sm:gap-3">
                        <select id="lead_filter_status" onchange="filterLeads()" class="text-xs sm:text-sm px-3 py-2.5 rounded-xl border border-slate-200 bg-white font-medium text-slate-700 outline-none hover:border-slate-300">
                            <option value="all">📋 Barcha holatlar</option>
                            <option value="suspicious">⚠️ Faqat Shubhali Lidlar ({total_suspicious} ta)</option>
                            <option value="yangi">⚪ Yangi</option>
                            <option value="oylanyapti">💭 O'ylayapti</option>
                            <option value="boglandi">🟢 Bog'lanildi</option>
                            <option value="zahira">📦 Zahira (Keyingi oqim)</option>
                            <option value="rad">🔴 Rad / Ko'tarmadi</option>
                        </select>
                        <select id="lead_filter_course" onchange="filterLeads()" class="text-xs sm:text-sm px-3 py-2.5 rounded-xl border border-slate-200 bg-white font-medium text-slate-700 outline-none hover:border-slate-300">
                            {course_filter_options_html}
                        </select>
                        <select id="lead_filter_source" onchange="filterLeads()" class="text-xs sm:text-sm px-3 py-2.5 rounded-xl border border-slate-200 bg-white font-medium text-slate-700 outline-none hover:border-slate-300">
                            <option value="all">📍 Barcha manbalar</option>
                            <option value="reels">🎬 Reels / Video izohi</option>
                            <option value="direct">💬 Instagram Direct</option>
                        </select>
                        <select id="lead_filter_manager" onchange="filterLeads()" class="text-xs sm:text-sm px-3 py-2.5 rounded-xl border border-slate-200 bg-white font-medium text-slate-700 outline-none hover:border-slate-300">
                            <option value="all">👥 Barcha xodimlar</option>
                            <option value="my_leads">⭐ Faqat mening lidlarim ({curr_display_name})</option>
                            <option value="unassigned">⚪ Biriktirilmagan lidlar</option>
                            {operators_filter_options_html}
                        </select>
                        <form action="/admin/sync-instagram" method="POST" class="inline" onsubmit="this.querySelector('button').innerHTML = '⏳ Sinxronlanmoqda...';">
                            <button type="submit" title="Instagram Direct yozishmalaridan lidlarni yangilash va tiklash" class="px-3.5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white rounded-xl text-xs sm:text-sm font-semibold flex items-center gap-1.5 shadow-sm transition whitespace-nowrap cursor-pointer">
                                🔄 Yangilash
                            </button>
                        </form>
                    </div>
                </div>

                <!-- 1. KANBAN USTUNLAR (PIPELINE) KO'RINIShI -->
                <div id="leads_kanban_view" class="overflow-x-auto pb-4 pt-1">
                    <div class="flex gap-3.5 items-start min-w-max">
                        {kanban_columns_html}
                    </div>
                </div>

                <!-- 2. JADVAL KO'RINIShI -->
                <div id="leads_table_view" class="overflow-x-auto rounded-xl border border-slate-100 hidden">
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
                                {leads_header_action_th}
                            </tr>
                        </thead>
                        <tbody>
                            {clients_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        {analytics_tab_html}
        {audit_tab_html}
        {operators_tab_html}
        {admin_only_tabs_html}
    </main>

    {common_modals_html}

    <!-- JavaScript: Qidiruv, Tab almashtirish va Chart.js -->
    <script>
        // ------------------ INSTAGRAM DIRECT CHAT VA AI BOSHQARUVI ------------------
        let currentChatClientId = null;
        let currentChatAiPaused = false;
        let currentChatInstagramId = null;
        let currentChatUsername = "";

        function escapeChatHtml(str) {{
            if (!str) return "";
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }}

        function openInstagramChatModal(clientId, clientName, username, campaign, aiPaused, instagramId) {{
            currentChatClientId = clientId;
            currentChatAiPaused = Boolean(Number(aiPaused) === 1);
            currentChatInstagramId = instagramId;
            currentChatUsername = username || "";

            const nameEl = document.getElementById("chatModalClientName");
            if (nameEl) nameEl.textContent = clientName || "Mijoz";

            const userEl = document.getElementById("chatModalUsername");
            if (userEl) {{
                userEl.textContent = username ? "@" + username : (instagramId ? "ID: " + instagramId : "");
                userEl.href = username ? "https://instagram.com/" + username : "#";
                if (!username) userEl.removeAttribute("href");
            }}

            const igBtn = document.getElementById("chatModalOpenIgBtn");
            if (igBtn) {{
                if (username) {{
                    igBtn.href = "https://instagram.com/" + username;
                    igBtn.classList.remove("hidden");
                }} else {{
                    igBtn.classList.add("hidden");
                }}
            }}

            const courseEl = document.getElementById("chatModalCourseBadge");
            if (courseEl) courseEl.textContent = "Yo'nalish: " + (campaign || "Umumiy");

            updateChatModalAiBadge(currentChatAiPaused);

            const modal = document.getElementById("instagramChatModal");
            if (modal) modal.classList.remove("hidden");

            const input = document.getElementById("chatInputText");
            if (input) {{
                input.value = "";
                input.focus();
            }}

            loadChatMessages(clientId);
        }}

        function closeChatModal() {{
            const modal = document.getElementById("instagramChatModal");
            if (modal) modal.classList.add("hidden");
            currentChatClientId = null;
        }}

        function updateChatModalAiBadge(isPaused) {{
            currentChatAiPaused = Boolean(isPaused);
            const badge = document.getElementById("chatModalAiBadge");
            const btn = document.getElementById("chatModalToggleAiBtn");
            const notice = document.getElementById("chatModalAiNotice");

            if (isPaused) {{
                if (badge) {{
                    badge.className = "text-[11px] font-bold px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 border border-amber-200";
                    badge.innerHTML = "🛑 AI To'xtatilgan (Inson nazorati)";
                }}
                if (btn) {{
                    btn.className = "text-xs font-bold px-3 py-1.5 rounded-xl border transition flex items-center gap-1.5 cursor-pointer shadow-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border-emerald-200";
                    btn.innerHTML = "<span>▶️</span> <span>AI ni qayta yoqish</span>";
                }}
                if (notice) notice.classList.remove("hidden");
            }} else {{
                if (badge) {{
                    badge.className = "text-[11px] font-bold px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 border border-emerald-200";
                    badge.innerHTML = "⚡ AI Faol (Avtomatik)";
                }}
                if (btn) {{
                    btn.className = "text-xs font-bold px-3 py-1.5 rounded-xl border transition flex items-center gap-1.5 cursor-pointer shadow-xs bg-amber-50 hover:bg-amber-100 text-amber-700 border-amber-200";
                    btn.innerHTML = "<span>⏸️</span> <span>AI ni to'xtatish</span>";
                }}
                if (notice) notice.classList.add("hidden");
            }}
        }}

        async function loadChatMessages(clientId) {{
            const box = document.getElementById("chatMessagesBox");
            if (!box) return;

            box.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full text-slate-400 py-12">
                    <div class="w-8 h-8 border-3 border-purple-600 border-t-transparent rounded-full animate-spin mb-3"></div>
                    <span class="text-xs font-medium">Suhbat tarixi yuklanmoqda...</span>
                </div>
            `;

            try {{
                const resp = await fetch("/admin/clients/" + clientId + "/chat");
                if (!resp.ok) {{
                    box.innerHTML = '<div class="text-center py-10 text-rose-500 text-xs">Suhbat tarixini yuklab bo\\'lmadi.</div>';
                    return;
                }}
                const data = await resp.json();
                if (!data.success) {{
                    box.innerHTML = '<div class="text-center py-10 text-rose-500 text-xs">' + (data.error || "Xatolik yuz berdi") + '</div>';
                    return;
                }}

                updateChatModalAiBadge(data.ai_paused);
                renderChatMessages(data.chat_history || []);
            }} catch (err) {{
                console.error("loadChatMessages error:", err);
                box.innerHTML = '<div class="text-center py-10 text-rose-500 text-xs">Server bilan bog\\'lanishda xatolik.</div>';
            }}
        }}

        function renderChatMessages(history) {{
            const box = document.getElementById("chatMessagesBox");
            if (!box) return;

            if (!history || history.length === 0) {{
                box.innerHTML = `
                    <div class="flex flex-col items-center justify-center h-full text-slate-400 py-12 text-center">
                        <div class="text-4xl mb-2">💬</div>
                        <div class="text-xs font-semibold text-slate-600">Hozircha suhbat xabarlari yo'q</div>
                        <div class="text-[11px] text-slate-400 max-w-xs mt-1">Quyidagi maydon orqali mijozga Instagram Directda birinchi xabarni yozishingiz mumkin.</div>
                    </div>
                `;
                return;
            }}

            let html = "";
            history.forEach(msg => {{
                const role = msg.role || "user";
                const text = escapeChatHtml(msg.text || "").replace(/\\n/g, "<br>");
                const time = msg.time || "";
                const manager = escapeChatHtml(msg.manager || "Mutaxassis");

                if (role === "user" || role === "client") {{
                    html += `
                        <div class="flex items-start gap-2 max-w-[85%]">
                            <div class="w-7 h-7 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                                👤
                            </div>
                            <div>
                                <div class="bg-white border border-slate-200 rounded-2xl rounded-tl-xs px-3.5 py-2.5 text-xs text-slate-800 shadow-2xs leading-relaxed">
                                    ${{text}}
                                </div>
                                <div class="text-[10px] text-slate-400 mt-0.5 pl-1">${{time ? time + " • " : ""}}Mijoz</div>
                            </div>
                        </div>
                    `;
                }} else if (role === "manager" || role === "operator") {{
                    html += `
                        <div class="flex items-start gap-2 max-w-[85%] ml-auto flex-row-reverse">
                            <div class="w-7 h-7 rounded-full bg-purple-600 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                                👨‍💼
                            </div>
                            <div class="text-right">
                                <div class="bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-2xl rounded-tr-xs px-3.5 py-2.5 text-xs shadow-sm leading-relaxed text-left">
                                    ${{text}}
                                </div>
                                <div class="text-[10px] text-purple-600 font-semibold mt-0.5 pr-1">${{time ? time + " • " : ""}}${{manager}}</div>
                            </div>
                        </div>
                    `;
                }} else {{
                    html += `
                        <div class="flex items-start gap-2 max-w-[85%]">
                            <div class="w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                                🤖
                            </div>
                            <div>
                                <div class="bg-indigo-50/80 border border-indigo-200/80 rounded-2xl rounded-tl-xs px-3.5 py-2.5 text-xs text-indigo-950 shadow-2xs leading-relaxed">
                                    ${{text}}
                                </div>
                                <div class="text-[10px] text-indigo-500 font-medium mt-0.5 pl-1">${{time ? time + " • " : ""}}AI Bot</div>
                            </div>
                        </div>
                    `;
                }}
            }});

            box.innerHTML = html;
            box.scrollTop = box.scrollHeight;
        }}

        async function sendDirectMessage(e) {{
            if (e) e.preventDefault();
            if (!currentChatClientId) return;

            const input = document.getElementById("chatInputText");
            const btn = document.getElementById("chatSendBtn");
            const text = input ? input.value.trim() : "";
            if (!text) return;

            if (input) input.disabled = true;
            if (btn) {{
                btn.disabled = true;
                btn.innerHTML = '<span>Yuborilmoqda...</span> <div class="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>';
            }}

            try {{
                const formData = new FormData();
                formData.append("message", text);

                const resp = await fetch("/admin/clients/" + currentChatClientId + "/send-message", {{
                    method: "POST",
                    body: formData
                }});

                const data = await resp.json();
                if (data.success) {{
                    if (input) input.value = "";
                    updateChatModalAiBadge(true);
                    showToast("✅ Xabar Instagram Directga yuborildi! AI ushbu mijoz uchun to'xtatildi.");

                    const box = document.getElementById("chatMessagesBox");
                    if (box) {{
                        const emptyPlaceholder = box.querySelector(".text-4xl");
                        if (emptyPlaceholder) box.innerHTML = "";

                        const nowTime = new Date().toLocaleTimeString().slice(0, 5);
                        const cleanHtml = escapeChatHtml(text).replace(/\\n/g, "<br>");
                        const newMsgHtml = `
                            <div class="flex items-start gap-2 max-w-[85%] ml-auto flex-row-reverse">
                                <div class="w-7 h-7 rounded-full bg-purple-600 text-white flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                                    👨‍💼
                                </div>
                                <div class="text-right">
                                    <div class="bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-2xl rounded-tr-xs px-3.5 py-2.5 text-xs shadow-sm leading-relaxed text-left">
                                        ${{cleanHtml}}
                                    </div>
                                    <div class="text-[10px] text-purple-600 font-semibold mt-0.5 pr-1">${{nowTime}} • Siz</div>
                                </div>
                            </div>
                        `;
                        box.insertAdjacentHTML("beforeend", newMsgHtml);
                        box.scrollTop = box.scrollHeight;
                    }}
                }} else {{
                    const err = data.error || "Xabarni yuborib bo'lmadi";
                    if (err.includes("Meta cheklovi") || err.includes("24 soat") || err.includes("oynasi tugagan")) {{
                        const igUrl = currentChatUsername ? ("https://instagram.com/" + currentChatUsername) : "";
                        const openIg = confirm(
                            "⚠️ " + err + "\\n\\n" +
                            "💡 Yechim: Ushbu mijozga Instagram ilovasi orqali to'g'ridan-to'g'ri yozishingiz mumkin (ilovada 24 soatlik API cheklovi yo'q).\\n\\n" +
                            (igUrl ? "Mijoz profilini Instagramda ochishni xohlaysizmi?" : "")
                        );
                        if (openIg && igUrl) {{
                            window.open(igUrl, "_blank");
                        }}
                    }} else {{
                        alert("Xatolik: " + err);
                    }}
                }}
            }} catch (err) {{
                console.error("sendDirectMessage error:", err);
                alert("Server bilan bog'lanishda xatolik yuz berdi");
            }} finally {{
                if (input) {{
                    input.disabled = false;
                    input.focus();
                }}
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span>Yuborish</span> <span>🚀</span>';
                }}
            }}
        }}

        async function toggleClientAi() {{
            if (!currentChatClientId) return;
            const newPausedState = !currentChatAiPaused;

            try {{
                const formData = new FormData();
                formData.append("ai_paused", newPausedState ? 1 : 0);

                const resp = await fetch("/admin/clients/" + currentChatClientId + "/toggle-ai", {{
                    method: "POST",
                    body: formData
                }});

                const data = await resp.json();
                if (data.success) {{
                    updateChatModalAiBadge(data.ai_paused);
                    if (data.ai_paused) {{
                        showToast("🛑 AI to'xtatildi! Mijozga faqat mutaxassis javob beradi.");
                    }} else {{
                        showToast("⚡ AI qayta yoqildi! Sun'iy intellekt mijozga avtomatik javob beradi.");
                    }}
                }} else {{
                    showToast("⚠️ Xatolik: " + (data.error || "Holatni o'zgartirib bo'lmadi"));
                }}
            }} catch (err) {{
                console.error("toggleClientAi error:", err);
                showToast("⚠️ Server bilan bog'lanishda xatolik");
            }}
        }}

        function insertQuickReply(text) {{
            const input = document.getElementById("chatInputText");
            if (input) {{
                input.value = text;
                input.focus();
            }}
        }}

        let currentModalClientId = null;
        let currentModalClientName = '';
        let currentModalUsername = '';
        let currentModalCampaign = '';
        let currentModalAiPaused = 0;
        let currentModalInstagramId = '';

        function openCommentModal(clientId, currentComment, clientName, currentStatus, currentPhone, username, campaign, currentManager, aiPaused, instagramId) {{
            currentModalClientId = clientId;
            currentModalClientName = clientName || '';
            currentModalUsername = username || '';
            currentModalCampaign = campaign || '';
            currentModalAiPaused = aiPaused || 0;
            currentModalInstagramId = instagramId || '';

            const form = document.getElementById('modalCommentForm');
            if (!form) return;
            form.action = '/admin/clients/' + clientId + '/comment';
            
            const titleElem = document.getElementById('modalClientTitle');
            if (titleElem) {{
                titleElem.textContent = (clientName || 'Mijoz') + (username ? ' (@' + username + ')' : '');
            }}
            const courseElem = document.getElementById('modalClientCourse');
            if (courseElem) {{
                courseElem.textContent = "Qiziqqan yo'nalishi: " + (campaign || 'Umumiy');
            }}
            
            const statusSelect = document.getElementById('modalStatusSelect');
            if (statusSelect) {{
                statusSelect.value = currentStatus || 'yangi';
            }}

            const managerSelect = document.getElementById('modalManagerSelect');
            if (managerSelect) {{
                managerSelect.value = currentManager || '';
                if (!managerSelect.value && currentManager) {{
                    const clean = currentManager.toLowerCase().replace('@', '').replace('_', ' ').trim();
                    for (let opt of managerSelect.options) {{
                        const optVal = opt.value.toLowerCase().replace('@', '').replace('_', ' ').trim();
                        if (optVal && (optVal === clean || optVal.includes(clean) || clean.includes(optVal))) {{
                            managerSelect.value = opt.value;
                            break;
                        }}
                    }}
                }}
            }}

            const phoneInput = document.getElementById('modalPhoneInput');
            const cleanPhone = (currentPhone && currentPhone !== '—' && currentPhone !== 'None') ? currentPhone : '';
            if (phoneInput) {{
                phoneInput.value = cleanPhone;
            }}

            const commentInput = document.getElementById('modalCommentInput');
            if (commentInput) {{
                commentInput.value = currentComment || '';
            }}

            const btnBox = document.getElementById('modalContactButtons');
            if (btnBox) {{
                let btnsHtml = '';
                const digits = cleanPhone.replace(/\\D/g, '');
                if (digits.length >= 9) {{
                    btnsHtml += '<a href="tel:' + cleanPhone + '" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-sm transition">📞 Qo\\'ng\\'iroq qilish</a>';
                    btnsHtml += '<a href="https://t.me/+' + digits + '" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-sky-500 hover:bg-sky-600 text-white text-xs font-bold shadow-sm transition">✈️ Telegramda yozish</a>';
                }} else {{
                    btnsHtml += '<span class="text-xs text-slate-400 bg-white px-2.5 py-1 rounded-lg border border-slate-200">📞 Raqam kiritilmagan</span>';
                }}
                if (clientId) {{
                    const safeName = (clientName || '').replace(/'/g, "\\\\'").replace(/\\n/g, ' ').replace(/\\r/g, ' ');
                    const safeCamp = (campaign || '').replace(/'/g, "\\\\'").replace(/\\n/g, ' ').replace(/\\r/g, ' ');
                    btnsHtml += '<button type="button" onclick="closeCommentModal(); openInstagramChatModal(\\'' + clientId + '\\', \\'' + safeName + '\\', \\'' + (username || '') + '\\', \\'' + safeCamp + '\\', ' + (aiPaused ? 1 : 0) + ', \\'' + (instagramId || '') + '\\')" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-pink-50 hover:bg-pink-100 text-pink-700 border border-pink-200 text-xs font-bold shadow-sm transition cursor-pointer">📸 CRM Direct Chat</button>';
                }}
                if (username) {{
                    btnsHtml += '<a href="https://instagram.com/' + username + '" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white text-xs font-bold shadow-sm transition">📸 Instagram Profil ↗</a>';
                }}
                btnBox.innerHTML = btnsHtml;
            }}

            const modal = document.getElementById('commentModal');
            if (modal) modal.classList.remove('hidden');
            if (commentInput) commentInput.focus();
        }}

        function assignToMe(name) {{
            const sel = document.getElementById('modalManagerSelect');
            if (sel) {{
                sel.value = name;
            }}
        }}

        function openPasswordChangeModal(opId, opName, opUser) {{
            const form = document.getElementById('opPasswordForm');
            const title = document.getElementById('opPasswordTitle');
            const sub = document.getElementById('opPasswordSubtitle');
            const modal = document.getElementById('opPasswordModal');
            if (form) form.action = '/admin/operators/' + opId + '/update-password';
            if (title) title.textContent = opName + ' uchun yangi parol';
            if (sub) sub.textContent = '@' + opUser + ' loginli operator parolini yangilash';
            if (modal) modal.classList.remove('hidden');
        }}

        function closeOpPasswordModal() {{
            const modal = document.getElementById('opPasswordModal');
            if (modal) modal.classList.add('hidden');
        }}

        function openDirectionsModal(opId, opName, allowedDirs) {{
            const form = document.getElementById('dirsForm');
            const title = document.getElementById('dirsModalTitle');
            const sub = document.getElementById('dirsModalSubtitle');
            const modal = document.getElementById('directionsModal');
            if (form) form.action = '/admin/operators/' + opId + '/update-directions';
            if (title) title.textContent = opName + ' — Yo\\'nalishlar';
            if (sub) sub.textContent = opName + ' uchun ko\\'rinadigan yo\\'nalishlarni belgilang';

            const isAll = (!allowedDirs || allowedDirs === 'all' || allowedDirs === '');
            const allowedList = isAll ? [] : allowedDirs.split(',').map(s => s.trim());
            const checks = form ? form.querySelectorAll('.modal-dir-check') : [];
            checks.forEach(ch => {{
                ch.checked = isAll ? true : allowedList.includes(ch.value);
            }});

            if (modal) modal.classList.remove('hidden');
        }}

        function closeDirectionsModal() {{
            const modal = document.getElementById('directionsModal');
            if (modal) modal.classList.add('hidden');
        }}

        function toggleAllModalDirections(val) {{
            const form = document.getElementById('dirsForm');
            if (!form) return;
            const checks = form.querySelectorAll('.modal-dir-check');
            checks.forEach(ch => {{ ch.checked = val; }});
        }}

        function toggleNewOpDirs(allCheck) {{
            const form = allCheck.closest('form');
            if (!form) return;
            const checks = form.querySelectorAll('.new-op-dir-check');
            checks.forEach(ch => {{
                if (allCheck.checked) ch.checked = false;
            }});
        }}

        function closeCommentModal() {{
            const modal = document.getElementById('commentModal');
            if (modal) modal.classList.add('hidden');
        }}

        async function saveCommentModal(e) {{
            e.preventDefault();
            const form = document.getElementById('modalCommentForm');
            if (!form) return;

            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {{
                submitBtn.innerHTML = '<span>⏳</span> <span>Saqlanmoqda...</span>';
                submitBtn.disabled = true;
            }}

            const clientId = currentModalClientId;
            try {{
                const formData = new FormData(form);
                const resp = await fetch(form.action, {{
                    method: 'POST',
                    body: formData,
                    headers: {{
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }}
                }});

                if (resp.ok) {{
                    const data = await resp.json();
                    const newStatus = data.lead_status;
                    const newComment = data.manager_comment || '';
                    const newPhone = data.phone_number || '';
                    const newManager = data.manager_name || '';
                    const newTime = data.manager_time || '';

                    // 1. Holat o'zgargan bo'lsa -> Kanban va Table'da harakatlantirish
                    if (newStatus && typeof quickMoveLead === 'function') {{
                        await quickMoveLead(clientId, newStatus);
                    }}

                    // 2. Telefon raqamni yangilash
                    if (newPhone) {{
                        const kPhone = document.getElementById('kanban_phone_' + clientId);
                        if (kPhone) kPhone.textContent = newPhone;
                        const rPhone = document.getElementById('row_phone_' + clientId);
                        if (rPhone) rPhone.textContent = newPhone;
                    }}

                    // 3. Mas'ul operator nomini yangilash
                    if (newManager) {{
                        const kMgr = document.getElementById('kanban_manager_' + clientId);
                        if (kMgr) kMgr.innerHTML = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold text-purple-700 bg-purple-50 border border-purple-100">👤 ' + escapeChatHtml(newManager) + '</span>';
                        const rMgr = document.getElementById('row_manager_' + clientId);
                        if (rMgr) rMgr.innerHTML = '<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold text-purple-700 bg-purple-50 border border-purple-100">👤 ' + escapeChatHtml(newManager) + '</span>';
                    }}

                    // 4. Izoh blokini yangilash
                    const kWrap = document.getElementById('kanban_comment_wrap_' + clientId);
                    const rWrap = document.getElementById('row_comment_wrap_' + clientId);
                    const commentHtml = newComment ? '<div class="p-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-950 text-[11px] shadow-2xs mt-1"><span class="font-bold text-amber-800">📝 Izoh:</span> ' + escapeChatHtml(newComment) + (newTime ? '<span class="block text-[10px] text-slate-400 mt-0.5 font-normal">' + newTime + '</span>' : '') + '</div>' : '';
                    if (kWrap) kWrap.innerHTML = commentHtml;
                    if (rWrap) rWrap.innerHTML = commentHtml;

                    // 5. Tugmalardagi onclick parametrlarini yangilash
                    const cleanPhone = newPhone || (document.getElementById('modalPhoneInput') ? document.getElementById('modalPhoneInput').value : '') || '';
                    const safeCommentJs = newComment.replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'").replace(/\\n/g, ' ');
                    const safeNameJs = (currentModalClientName || '').replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'");
                    const safeCampJs = (currentModalCampaign || '').replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'");
                    const safeMgrJs = newManager.replace(/\\\\/g, "\\\\\\\\").replace(/'/g, "\\\\'");

                    const newOnclick = "openCommentModal('" + clientId + "', '" + safeCommentJs + "', '" + safeNameJs + "', '" + (newStatus || 'yangi') + "', '" + cleanPhone + "', '" + currentModalUsername + "', '" + safeCampJs + "', '" + safeMgrJs + "', " + currentModalAiPaused + ", '" + currentModalInstagramId + "')";

                    const kBtn = document.getElementById('kanban_comment_btn_' + clientId);
                    if (kBtn) kBtn.setAttribute('onclick', newOnclick);
                    const rBtn = document.getElementById('table_action_comment_btn_' + clientId);
                    if (rBtn) rBtn.setAttribute('onclick', newOnclick);
                    const rRowBtn = document.getElementById('table_row_comment_btn_' + clientId);
                    if (rRowBtn) {{
                        rRowBtn.setAttribute('onclick', newOnclick);
                        rRowBtn.innerHTML = '💬 ' + (newComment ? "Izohni o'zgartirish" : "Izoh qo'shish");
                    }}

                    closeCommentModal();
                    showToast("✅ Ma'lumotlar saqlandi va Telegramga yuborildi!");
                }} else {{
                    showToast("⚠️ Saqlashda xatolik yuz berdi");
                }}
            }} catch (err) {{
                console.error('saveCommentModal error:', err);
                showToast("⚠️ Server bilan bog'lanishda xatolik");
            }} finally {{
                if (submitBtn) {{
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }}
            }}
        }}

        async function deleteLeadAjax(clientId) {{
            if (!confirm("Haqiqatan ham ushbu lidni o'chirmoqchimisiz?")) return;
            try {{
                const resp = await fetch('/admin/clients/' + clientId + '/delete', {{
                    method: 'POST',
                    headers: {{
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }}
                }});
                if (resp.ok) {{
                    const card = document.getElementById('kanban_card_' + clientId);
                    if (card) card.remove();
                    const row = document.querySelector(`.client-row[data-client-id="${{clientId}}"]`);
                    if (row) row.remove();
                    updateKanbanCounts();
                    showToast("🗑️ Lid muvaffaqiyatli o'chirildi");
                }} else {{
                    showToast("⚠️ O'chirishda xatolik yuz berdi");
                }}
            }} catch (err) {{
                console.error('deleteLeadAjax error:', err);
                showToast("⚠️ Server bilan bog'lanishda xatolik");
            }}
        }}

        async function saveDirectionsModal(e) {{
            e.preventDefault();
            const form = document.getElementById('dirsForm');
            if (!form) return;
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {{
                submitBtn.innerHTML = '⏳ Saqlanmoqda...';
                submitBtn.disabled = true;
            }}

            try {{
                const formData = new FormData(form);
                const resp = await fetch(form.action, {{
                    method: 'POST',
                    body: formData,
                    headers: {{
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }}
                }});

                if (resp.ok) {{
                    const data = await resp.json();
                    const opId = data.op_id;
                    const displayDirs = data.display_dirs || 'Barcha yo\\'nalishlar';
                    const tdEl = document.getElementById('op_dirs_td_' + opId);
                    if (tdEl) {{
                        tdEl.innerHTML = data.badges_html || ('<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-blue-50 text-blue-700 border border-blue-200 shadow-2xs">' + escapeChatHtml(displayDirs) + '</span>');
                    }}
                    closeDirectionsModal();
                    showToast("✅ Mutaxassis yo'nalishlari muvaffaqiyatli saqlandi!");
                }} else {{
                    showToast("⚠️ Saqlashda xatolik yuz berdi");
                }}
            }} catch (err) {{
                console.error('saveDirectionsModal error:', err);
                showToast("⚠️ Server bilan bog'lanishda xatolik");
            }} finally {{
                if (submitBtn) {{
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }}
            }}
        }}

        async function saveOpPasswordModal(e) {{
            e.preventDefault();
            const form = document.getElementById('opPasswordForm');
            if (!form) return;
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn ? submitBtn.innerHTML : '';
            if (submitBtn) {{
                submitBtn.innerHTML = '⏳ Saqlanmoqda...';
                submitBtn.disabled = true;
            }}

            try {{
                const formData = new FormData(form);
                const resp = await fetch(form.action, {{
                    method: 'POST',
                    body: formData,
                    headers: {{
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }}
                }});

                if (resp.ok) {{
                    closeOpPasswordModal();
                    form.reset();
                    showToast("✅ Mutaxassis paroli muvaffaqiyatli yangilandi!");
                }} else {{
                    showToast("⚠️ Parolni yangilashda xatolik yuz berdi");
                }}
            }} catch (err) {{
                console.error('saveOpPasswordModal error:', err);
                showToast("⚠️ Server bilan bog'lanishda xatolik");
            }} finally {{
                if (submitBtn) {{
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }}
            }}
        }}

        document.addEventListener('click', function(e) {{
            const modal = document.getElementById('commentModal');
            if (modal && e.target === modal) {{
                closeCommentModal();
            }}
            const opModal = document.getElementById('opPasswordModal');
            if (opModal && e.target === opModal) {{
                closeOpPasswordModal();
            }}
            const dirsModal = document.getElementById('directionsModal');
            if (dirsModal && e.target === dirsModal) {{
                closeDirectionsModal();
            }}
            const chatModal = document.getElementById('instagramChatModal');
            if (chatModal && e.target === chatModal) {{
                closeChatModal();
            }}
        }});

        function switchTab(tabId) {{
            try {{
                // Barcha tab kontentlarini yashirish
                document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
                // Barcha tugmalardan active klassini olish
                document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));

                // Tanlangan tabni ochish
                const content = document.getElementById('tab_' + tabId);
                const btn = document.getElementById('tab_btn_' + tabId);
                if (content) content.classList.remove('hidden');
                if (btn) btn.classList.add('active');

                try {{
                    window.location.hash = tabId;
                }} catch (e) {{}}

                // Agar Statistika tabi ochilsa chartlarni render qilish
                if (tabId === 'analytics') {{
                    setTimeout(() => {{
                        try {{
                            if (typeof initOrUpdateAnalyticsCharts === 'function') {{
                                initOrUpdateAnalyticsCharts();
                            }}
                        }} catch (err) {{
                            console.warn('Chart error:', err);
                        }}
                    }}, 50);
                }}
            }} catch (err) {{
                console.error('switchTab error:', err);
            }}
        }}

        // Sahifa yuklanganda yoki hash o'zgarganda tabni ochish
        function applyHashTab() {{
            try {{
                const hash = window.location.hash.replace('#', '');
                if (hash && document.getElementById('tab_' + hash)) {{
                    switchTab(hash);
                }}
            }} catch (e) {{}}
        }}

        window.addEventListener('DOMContentLoaded', () => {{
            applyHashTab();

            try {{
                const savedMode = localStorage.getItem('leads_view_mode') || 'kanban';
                setViewMode(savedMode);
            }} catch (e) {{
                setViewMode('kanban');
            }}
        }});

        window.addEventListener('hashchange', applyHashTab);

        let chartsInitialized = false;
        let chartInstances = {{}};

        function initOrUpdateAnalyticsCharts() {{
            if (typeof Chart === 'undefined') {{
                console.warn('Chart.js kutubxonasi hali yuklanmadi');
                return;
            }}
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
                        labels: ["⚪ Yangi", "💭 O'ylayapti", "🟢 Bog'lanildi", "📦 Zahira", "🔴 Rad"],
                        datasets: [{{
                            data: [{new_leads}, {thinking_leads}, {done_leads}, {reserve_leads}, {rejected_leads}],
                            backgroundColor: ['#94a3b8', '#0284c7', '#10b981', '#8b5cf6', '#f43f5e'],
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

        // Lidlar jadvalida tezkor qidiruv va filtrlash
        function filterLeads() {{
            const searchVal = document.getElementById('lead_search').value.toLowerCase().trim();
            const statusVal = document.getElementById('lead_filter_status').value;
            const courseVal = document.getElementById('lead_filter_course') ? document.getElementById('lead_filter_course').value : 'all';
            const sourceVal = document.getElementById('lead_filter_source') ? document.getElementById('lead_filter_source').value : 'all';
            const managerVal = document.getElementById('lead_filter_manager') ? document.getElementById('lead_filter_manager').value : 'all';
            const rows = document.querySelectorAll('.client-row');

            let visibleCount = 0;
            rows.forEach(row => {{
                const searchData = row.getAttribute('data-search') || '';
                const statusData = row.getAttribute('data-status') || '';
                const courseData = row.getAttribute('data-course') || '';
                const sourceData = row.getAttribute('data-source') || '';
                const managerData = (row.getAttribute('data-manager') || '').toLowerCase().trim();

                const matchesSearch = !searchVal || searchData.includes(searchVal);
                const isRowSuspicious = (row.getAttribute('data-suspicious') === '1');
                const matchesStatus = (statusVal === 'all') || (statusVal === 'suspicious' ? isRowSuspicious : (statusData === statusVal));

                let matchesCourse = true;
                if (courseVal !== 'all') {{
                    if (courseVal === 'front_office' || courseVal === 'onlayn') {{
                        matchesCourse = courseData.includes('front') || courseData.includes('housekeeping') || courseData.includes('tourism-edu') || courseData.includes('onlayn') || courseData.includes('online');
                    }} else if (courseVal === 'hotel') {{
                        matchesCourse = courseData.includes('hotel') || courseData.includes('mehmonxona') || courseData.includes('operations');
                    }} else if (courseVal === 'gid_malaka') {{
                        matchesCourse = courseData.includes('malaka');
                    }} else if (courseVal === 'gid_qayta') {{
                        matchesCourse = (courseData.includes('gid') || courseData.includes('ekskurs')) && !courseData.includes('malaka');
                    }} else if (courseVal === 'turagent') {{
                        matchesCourse = courseData.includes('turagent');
                    }} else if (courseVal === 'turoperator') {{
                        matchesCourse = courseData.includes('turoperator');
                    }} else if (courseVal === 'narx') {{
                        matchesCourse = courseData.includes('narx');
                    }} else if (courseVal === 'dastur') {{
                        matchesCourse = courseData.includes('dastur');
                    }} else if (courseVal === 'konsultatsiya') {{
                        matchesCourse = courseData.includes('konsultatsiya') || courseData.includes('batafsil');
                    }} else if (courseVal === 'umumiy') {{
                        matchesCourse = courseData.includes('umumiy') || (!courseData.includes('hotel') && !courseData.includes('gid') && !courseData.includes('turagent') && !courseData.includes('turoperator') && !courseData.includes('front') && !courseData.includes('onlayn'));
                    }}
                }}

                let matchesSource = true;
                if (sourceVal !== 'all') {{
                    if (sourceVal === 'reels') {{
                        matchesSource = sourceData.includes('reel') || sourceData.includes('instagram.com/reel') || sourceData.includes('instagram.com/p') || sourceData.includes('izoh') || sourceData.includes('video');
                    }} else if (sourceVal === 'direct') {{
                        matchesSource = !sourceData.includes('reel') && !sourceData.includes('instagram.com/reel') && !sourceData.includes('instagram.com/p') && !sourceData.includes('izoh') && !sourceData.includes('video');
                    }}
                }}

                let matchesManager = true;
                if (managerVal !== 'all') {{
                    if (managerVal === 'my_leads') {{
                        matchesManager = managerData.includes('{curr_display_name.lower()}');
                    }} else if (managerVal === 'unassigned') {{
                        matchesManager = !managerData || managerData === '—' || managerData === 'biriktirilmagan' || managerData === 'yangi' || managerData === 'none' || managerData === '';
                    }} else {{
                        matchesManager = managerData.includes(managerVal.toLowerCase());
                    }}
                }}

                if (matchesSearch && matchesStatus && matchesCourse && matchesSource && matchesManager) {{
                    row.style.display = '';
                    visibleCount++;
                }} else {{
                    row.style.display = 'none';
                }}
            }});

            const cards = document.querySelectorAll('.kanban-card');
            cards.forEach(card => {{
                const searchData = card.getAttribute('data-search') || '';
                const statusData = card.getAttribute('data-status') || '';
                const courseData = card.getAttribute('data-course') || '';
                const sourceData = card.getAttribute('data-source') || '';
                const managerData = (card.getAttribute('data-manager') || '').toLowerCase().trim();

                const matchesSearch = !searchVal || searchData.includes(searchVal);
                const isCardSuspicious = (card.getAttribute('data-suspicious') === '1');
                const matchesStatus = (statusVal === 'all') || (statusVal === 'suspicious' ? isCardSuspicious : (statusData === statusVal));

                let matchesCourse = true;
                if (courseVal !== 'all') {{
                    if (courseVal === 'front_office' || courseVal === 'onlayn') {{
                        matchesCourse = courseData.includes('front') || courseData.includes('housekeeping') || courseData.includes('tourism-edu') || courseData.includes('onlayn') || courseData.includes('online');
                    }} else if (courseVal === 'hotel') {{
                        matchesCourse = courseData.includes('hotel') || courseData.includes('mehmonxona') || courseData.includes('operations');
                    }} else if (courseVal === 'gid_malaka') {{
                        matchesCourse = courseData.includes('malaka');
                    }} else if (courseVal === 'gid_qayta') {{
                        matchesCourse = (courseData.includes('gid') || courseData.includes('ekskurs')) && !courseData.includes('malaka');
                    }} else if (courseVal === 'turagent') {{
                        matchesCourse = courseData.includes('turagent');
                    }} else if (courseVal === 'turoperator') {{
                        matchesCourse = courseData.includes('turoperator');
                    }} else if (courseVal === 'narx') {{
                        matchesCourse = courseData.includes('narx');
                    }} else if (courseVal === 'dastur') {{
                        matchesCourse = courseData.includes('dastur');
                    }} else if (courseVal === 'konsultatsiya') {{
                        matchesCourse = courseData.includes('konsultatsiya') || courseData.includes('batafsil');
                    }} else if (courseVal === 'umumiy') {{
                        matchesCourse = courseData.includes('umumiy') || (!courseData.includes('hotel') && !courseData.includes('gid') && !courseData.includes('turagent') && !courseData.includes('turoperator') && !courseData.includes('front') && !courseData.includes('onlayn'));
                    }}
                }}

                let matchesSource = true;
                if (sourceVal !== 'all') {{
                    if (sourceVal === 'reels') {{
                        matchesSource = sourceData.includes('reel') || sourceData.includes('instagram.com/reel') || sourceData.includes('instagram.com/p') || sourceData.includes('izoh') || sourceData.includes('video');
                    }} else if (sourceVal === 'direct') {{
                        matchesSource = !sourceData.includes('reel') && !sourceData.includes('instagram.com/reel') && !sourceData.includes('instagram.com/p') && !sourceData.includes('izoh') && !sourceData.includes('video');
                    }}
                }}

                let matchesManager = true;
                if (managerVal !== 'all') {{
                    if (managerVal === 'my_leads') {{
                        matchesManager = managerData.includes('{curr_display_name.lower()}');
                    }} else if (managerVal === 'unassigned') {{
                        matchesManager = !managerData || managerData === '—' || managerData === 'biriktirilmagan' || managerData === 'yangi' || managerData === 'none' || managerData === '';
                    }} else {{
                        matchesManager = managerData.includes(managerVal.toLowerCase());
                    }}
                }}

                if (matchesSearch && matchesStatus && matchesCourse && matchesSource && matchesManager) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            updateKanbanCounts();
        }}

        function updateKanbanCounts() {{
            const colStatuses = ['yangi', 'oylanyapti', 'boglandi', 'zahira', 'rad'];
            colStatuses.forEach(st => {{
                const colBox = document.getElementById('kanban_col_' + st);
                if (colBox) {{
                    const visibleCards = colBox.querySelectorAll('.kanban-card:not([style*="display: none"])').length;
                    const badge = document.getElementById('badge_count_' + st);
                    if (badge) badge.textContent = visibleCards + ' ta';
                }}
            }});
        }}

        function filterSuspiciousLeads() {{
            switchTab('leads');
            const sel = document.getElementById('lead_filter_status');
            if (sel) {{
                sel.value = 'suspicious';
                filterLeads();
            }}
        }}

        const statusTitles = {{
            "yangi": "⚪ Yangi Lid",
            "boglandi": "🟢 Bog'lanildi",
            "oylanyapti": "💭 O'ylayapti",
            "zahira": "📦 Zahira (Keyingi oqim)",
            "rad": "🔴 Rad / Ko'tarmadi"
        }};

        function setViewMode(mode) {{
            const kanbanBox = document.getElementById('leads_kanban_view');
            const tableBox = document.getElementById('leads_table_view');
            const btnKanban = document.getElementById('view_btn_kanban');
            const btnTable = document.getElementById('view_btn_table');

            if (mode === 'table') {{
                if (kanbanBox) kanbanBox.classList.add('hidden');
                if (tableBox) tableBox.classList.remove('hidden');
                if (btnTable) {{
                    btnTable.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition bg-white text-purple-700 shadow-xs cursor-pointer';
                }}
                if (btnKanban) {{
                    btnKanban.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition text-slate-600 hover:text-slate-900 cursor-pointer';
                }}
                try {{ localStorage.setItem('leads_view_mode', 'table'); }} catch (e) {{}}
            }} else {{
                if (kanbanBox) kanbanBox.classList.remove('hidden');
                if (tableBox) tableBox.classList.add('hidden');
                if (btnKanban) {{
                    btnKanban.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition bg-white text-purple-700 shadow-xs cursor-pointer';
                }}
                if (btnTable) {{
                    btnTable.className = 'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition text-slate-600 hover:text-slate-900 cursor-pointer';
                }}
                try {{ localStorage.setItem('leads_view_mode', 'kanban'); }} catch (e) {{}}
            }}
            filterLeads();
        }}

        let draggedClientId = null;
        let draggedOldStatus = null;

        function handleDragStart(e, clientId, oldStatus) {{
            draggedClientId = clientId;
            draggedOldStatus = oldStatus;
            e.dataTransfer.setData('text/plain', clientId);
            e.dataTransfer.effectAllowed = 'move';
            const card = document.getElementById('kanban_card_' + clientId);
            if (card) {{
                card.classList.add('opacity-40', 'scale-95');
            }}
        }}

        function handleDragEnd(e, clientId) {{
            const card = document.getElementById('kanban_card_' + clientId);
            if (card) {{
                card.classList.remove('opacity-40', 'scale-95');
            }}
            document.querySelectorAll('.kanban-col').forEach(col => {{
                col.classList.remove('ring-2', 'ring-purple-400', 'bg-purple-50/50');
            }});
        }}

        function handleDragOver(e) {{
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            const col = e.currentTarget;
            col.classList.add('ring-2', 'ring-purple-400', 'bg-purple-50/50');
        }}

        function handleDragLeave(e) {{
            const col = e.currentTarget;
            col.classList.remove('ring-2', 'ring-purple-400', 'bg-purple-50/50');
        }}

        async function handleDrop(e, newStatus) {{
            e.preventDefault();
            const col = e.currentTarget;
            col.classList.remove('ring-2', 'ring-purple-400', 'bg-purple-50/50');
            const clientId = e.dataTransfer.getData('text/plain') || draggedClientId;
            if (!clientId) return;

            const card = document.getElementById('kanban_card_' + clientId);
            if (card) {{
                card.classList.remove('opacity-40', 'scale-95');
            }}

            if (draggedOldStatus === newStatus) return;

            await quickMoveLead(clientId, newStatus);
        }}

        async function quickMoveLead(clientId, newStatus) {{
            const card = document.getElementById('kanban_card_' + clientId);
            const targetCol = document.getElementById('kanban_col_' + newStatus);

            // Optimistic UI move
            if (card && targetCol) {{
                const emptyPlaceholder = targetCol.querySelector('.empty-col-placeholder');
                if (emptyPlaceholder) emptyPlaceholder.remove();

                targetCol.prepend(card);
                card.setAttribute('data-status', newStatus);
                const sel = card.querySelector('select');
                if (sel) sel.value = newStatus;
            }}

            // Jadval qatorini ham yangilash
            const tableRow = document.querySelector(`.client-row[data-client-id="${{clientId}}"]`);
            if (tableRow) {{
                tableRow.setAttribute('data-status', newStatus);
                const trSel = tableRow.querySelector('select[name="status"]');
                if (trSel) trSel.value = newStatus;
            }}

            updateKanbanCounts();

            // Serverga AJAX yuborish
            try {{
                const formData = new FormData();
                formData.append('status', newStatus);
                formData.append('manager_name', '{curr_display_name}');

                const resp = await fetch('/admin/clients/' + clientId + '/status', {{
                    method: 'POST',
                    body: formData,
                    headers: {{
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }}
                }});

                if (resp.ok) {{
                    showToast("✅ Lid holati yangilandi: " + (statusTitles[newStatus] || newStatus));
                }} else {{
                    showToast("⚠️ Holatni saqlashda xatolik yuz berdi");
                }}
            }} catch (err) {{
                console.error('quickMoveLead error:', err);
                showToast("⚠️ Server bilan bog'lanishda xatolik");
            }}
        }}

        function showToast(msg) {{
            const toast = document.getElementById('toastNotification');
            const msgEl = document.getElementById('toastMessage');
            if (!toast || !msgEl) return;
            msgEl.innerHTML = msg;
            toast.classList.remove('translate-y-24', 'opacity-0');
            toast.classList.add('translate-y-0', 'opacity-100');
            setTimeout(() => {{
                toast.classList.remove('translate-y-0', 'opacity-100');
                toast.classList.add('translate-y-24', 'opacity-0');
            }}, 2800);
        }}

        const LEADS_DATA = {clients_json_data};

        // Microsoft Excel (.xlsx) formatida to'liq formatlangan holda yuklab olish (Brauzer xatoliksiz)
        async function exportLeadsToExcel(btn) {{
            const originalText = btn ? btn.innerHTML : '';
            if (btn) {{
                btn.innerHTML = '⏳ Tayyorlanmoqda...';
                btn.disabled = true;
            }}

            try {{
                // 1. Avval serverdagi to'liq formatlangan chiroyli Excel faylini yuklab olamiz
                const resp = await fetch('/api/clients/excel');
                if (resp.ok) {{
                    const blob = await resp.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    const nowStr = new Date().toISOString().slice(0, 10);
                    a.download = `XTA_Instagram_Lidlar_${{nowStr}}.xlsx`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                    return;
                }}
                throw new Error("Server Excel xatosi");
            }} catch (err) {{
                console.warn("Serverdan yuklab bo'lmadi, brauzer orqali yuklanmoqda:", err);
                // Brauzer orqali zaxira yuklash (SheetJS)
                try {{
                    if (typeof XLSX !== 'undefined') {{
                        const statusMap = {{
                            "yangi": "⚪ Yangi",
                            "boshlangich": "⚪ Yangi",
                            "boglandi": "🟢 Bog'lanildi",
                            "bog'landi": "🟢 Bog'lanildi",
                            "jarayonda": "🟢 Bog'lanildi",
                            "oylanyapti": "💭 O'ylayapti",
                            "o'ylayapti": "💭 O'ylayapti",
                            "zahira": "📦 Zahira (Keyingi oqim)",
                            "zaxira": "📦 Zahira (Keyingi oqim)",
                            "rad": "🔴 Rad / Ko'tarmadi"
                        }};

                        const rows = LEADS_DATA.map((c, i) => ({{
                            "№": c.id || (i + 1),
                            "Sana va Vaqt": c.created_at || '—',
                            "Mijoz Ismi": c.full_name || 'Kiritilmagan',
                            "Telefon Raqami": c.phone_number ? String(c.phone_number) : '—',
                            "Yo'nalish / Kurs": c.campaign || 'Umumiy',
                            "Manba": c.source || 'Direct',
                            "Holati": statusMap[c.lead_status] || c.lead_status || '⚪ Yangi',
                            "Instagram Username": c.username ? '@' + c.username : '—',
                            "Obuna": c.is_follower ? '⭐ Obunachi' : 'Obuna emas',
                            "Oxirgi Xabar": (c.last_message || '—').replace(/[\\r\\n]+/g, ' '),
                            "AI Ehtiyoj Tahlili": (c.ai_summary || '—').replace(/[\\r\\n]+/g, ' '),
                            "Mutaxassis Izohi": (c.manager_comment || '—').replace(/[\\r\\n]+/g, ' '),
                            "Mas'ul Xodim": c.manager_name || '—'
                        }}));

                        const ws = XLSX.utils.json_to_sheet(rows);
                        ws['!cols'] = [
                            {{ wch: 6 }},
                            {{ wch: 18 }},
                            {{ wch: 22 }},
                            {{ wch: 18 }},
                            {{ wch: 28 }},
                            {{ wch: 32 }},
                            {{ wch: 18 }},
                            {{ wch: 20 }},
                            {{ wch: 14 }},
                            {{ wch: 35 }},
                            {{ wch: 35 }},
                            {{ wch: 25 }},
                            {{ wch: 15 }}
                        ];
                        const wb = XLSX.utils.book_new();
                        XLSX.utils.book_append_sheet(wb, ws, "Lidlar");
                        const nowStr = new Date().toISOString().slice(0, 10);
                        XLSX.writeFile(wb, `XTA_Instagram_Lidlar_${{nowStr}}.xlsx`);
                    }} else {{
                        downloadCSVDirectly();
                    }}
                }} catch (e2) {{
                    downloadCSVDirectly();
                }}
            }} finally {{
                if (btn) {{
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }}
            }}
        }}

        // CSV formatida yuklab olish (UTF-8 BOM va regional ajratuvchilar bilan)
        function downloadCSVDirectly() {{
            const statusMap = {{
                "yangi": "⚪ Yangi",
                "boshlangich": "⚪ Yangi",
                "boglandi": "🟢 Bog'lanildi",
                "bog'landi": "🟢 Bog'lanildi",
                "jarayonda": "🟢 Bog'lanildi",
                "oylanyapti": "💭 O'ylayapti",
                "o'ylayapti": "💭 O'ylayapti",
                "zahira": "📦 Zahira",
                "rad": "🔴 Rad / Ko'tarmadi"
            }};

            let csv = '\\ufeff'; // UTF-8 BOM Excel uchun
            const headers = ["ID", "Username", "Mijoz Ismi", "Telefon Raqami", "Yo'nalish / Kurs", "Manba", "Holati", "Obuna", "💡 AI Ehtiyoj Tahlili", "Oxirgi Xabar / So'rov", "Mas'ul Xodim", "Mutaxassis Izohi", "Yaratilgan Vaqt", "Instagram ID", "Profil Havolasi"];
            csv += headers.map(h => `"${{h}}"`).join(';') + '\\r\\n';

            LEADS_DATA.forEach((c, idx) => {{
                const row = [
                    c.id || (idx + 1),
                    c.username ? '@' + c.username : '—',
                    c.full_name || 'Kiritilmagan',
                    c.phone_number ? `="${{c.phone_number}}"` : '—',
                    c.campaign || 'Umumiy',
                    c.source || 'Direct',
                    statusMap[c.lead_status] || c.lead_status || '⚪ Yangi',
                    c.is_follower ? '⭐ Obunachi' : 'Obuna emas',
                    (c.ai_summary || '—').replace(/[\\r\\n]+/g, ' '),
                    (c.last_message || '—').replace(/[\\r\\n]+/g, ' '),
                    c.manager_name || '—',
                    (c.manager_comment || '—').replace(/[\\r\\n]+/g, ' '),
                    c.created_at || '—',
                    String(c.instagram_id || ''),
                    c.username ? 'https://instagram.com/' + c.username : ''
                ];
                csv += row.map(val => `"${{String(val).replace(/"/g, '""')}}"`).join(';') + '\\r\\n';
            }});

            const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `instagram_lidlar_${{new Date().toISOString().slice(0, 10)}}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}

        function exportLeadsToCSV(btn) {{
            const originalText = btn ? btn.innerHTML : '';
            if (btn) {{
                btn.innerHTML = '⏳ Yuklanmoqda...';
                btn.disabled = true;
            }}
            try {{
                downloadCSVDirectly();
            }} catch(err) {{
                console.error("CSV eksport xatoligi:", err);
            }} finally {{
                if (btn) {{
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }}
            }}
        }}

        {admin_scripts_js}
    </script>
</body>
</html>
"""
    return html
