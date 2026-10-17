def get_admin_dashboard_html(settings: dict, campaigns: list, clients: list, notice: str = "") -> str:
    # Aksiya ro'yxati HTML
    campaigns_html = ""
    if not campaigns:
        campaigns_html = """
        <tr>
            <td colspan="6" class="px-6 py-8 text-center text-gray-500">
                Hozircha maxsus video qoidalari yo'q. Quyidagi forma orqali yangi video aksiya qo'shishingiz mumkin.
            </td>
        </tr>
        """
    for c in campaigns:
        campaigns_html += f"""
        <tr class="border-b border-gray-100 hover:bg-gray-50 transition">
            <td class="px-6 py-4 font-semibold text-gray-800">{c['name']}</td>
            <td class="px-6 py-4"><span class="bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-xs font-medium">#{c.get('trigger_keyword', '—')}</span></td>
            <td class="px-6 py-4 text-xs text-gray-500 truncate max-w-xs">{c.get('public_reply', '—')}</td>
            <td class="px-6 py-4 text-xs text-blue-600 truncate max-w-xs"><a href="{c.get('promo_link', '#')}" target="_blank" class="hover:underline">{c.get('promo_link', '—')}</a></td>
            <td class="px-6 py-4">
                <form method="POST" action="/admin/campaign/delete" onsubmit="return confirm('Rostdan ham o\\'chirmoqchimisiz?');">
                    <input type="hidden" name="campaign_id" value="{c['id']}">
                    <button type="submit" class="text-red-500 hover:text-red-700 text-sm font-medium">O'chirish</button>
                </form>
            </td>
        </tr>
        """

    # Mijozlar ro'yxati HTML
    clients_html = ""
    if not clients:
        clients_html = """
        <tr>
            <td colspan="6" class="px-6 py-8 text-center text-gray-500">
                Hozircha lidlar yo'q. Mijozlar Instagramdan yozishi bilan bu yerda paydo bo'ladi.
            </td>
        </tr>
        """
    for client in clients:
        full_name = client.get('full_name') or "Kiritilmagan"
        phone = client.get('phone_number') or "—"
        source = client.get('source') or "Direct"
        campaign = client.get('campaign') or "Umumiy"
        created_at = client.get('created_at', '')[:16].replace("T", " ")

        clients_html += f"""
        <tr class="border-b border-gray-100 hover:bg-gray-50 transition">
            <td class="px-6 py-4 font-medium text-gray-900">{full_name}</td>
            <td class="px-6 py-4"><a href="tel:{phone}" class="font-mono text-blue-600 hover:underline">{phone}</a></td>
            <td class="px-6 py-4"><span class="bg-emerald-50 text-emerald-700 px-2.5 py-1 rounded text-xs font-medium">{campaign}</span></td>
            <td class="px-6 py-4 text-xs text-gray-500">{source}</td>
            <td class="px-6 py-4 text-xs text-gray-400">{created_at}</td>
        </tr>
        """

    notice_banner = f"""
    <div class="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm font-medium flex items-center justify-between">
        <span>✅ {notice}</span>
    </div>
    """ if notice else ""

    html = f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Instagram Bot Boshqaruv Paneli</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
        </style>
    </head>
    <body class="bg-slate-50 min-h-screen text-slate-800">
        <!-- Header -->
        <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div class="flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 via-pink-600 to-amber-500 flex items-center justify-center text-white font-bold text-lg shadow-md">
                        📸
                    </div>
                    <div>
                        <h1 class="text-xl font-bold text-slate-900">Instagram Bot Boshqaruvi</h1>
                        <p class="text-xs text-slate-500">Direct xabarlari, Video qoidalari va Lidlar bazasi</p>
                    </div>
                </div>
                <div class="flex items-center gap-3">
                    <a href="/api/clients/csv" class="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-xl text-sm font-medium shadow-sm transition">
                        📥 Excel (.CSV) yuklab olish
                    </a>
                </div>
            </div>
        </header>

        <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {notice_banner}

            <!-- Statistika -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Jami Lidlar (Mijozlar)</div>
                    <div class="text-3xl font-extrabold text-slate-900">{len(clients)} ta</div>
                </div>
                <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Aktiv Video Qoidalari</div>
                    <div class="text-3xl font-extrabold text-purple-600">{len(campaigns)} ta</div>
                </div>
                <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                    <div class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">Server Holati</div>
                    <div class="text-3xl font-extrabold text-emerald-600 flex items-center gap-2">
                        <span class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></span> 24/7 Jonli
                    </div>
                </div>
            </div>

            <!-- Tablar bo'limi -->
            <div class="space-y-8">
                <!-- 1. DIRECT XABAR SHABLONLARI -->
                <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                    <div class="border-b border-slate-100 pb-4 mb-6">
                        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                            💬 1. Direct Xabarlar Shabloni
                        </h2>
                        <p class="text-sm text-slate-500">Mijoz to'g'ridan-to'g'ri Directga yozganda bot ushbu matnlardan foydalanadi.</p>
                    </div>

                    <form method="POST" action="/admin/settings/save" class="space-y-6">
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-2">1. Salomlashish matni (Birinchi xabar):</label>
                            <textarea name="direct_welcome" rows="3" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm">{settings.get('direct_welcome', '')}</textarea>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <label class="block text-sm font-semibold text-slate-700 mb-2">2. Telefon raqam so'rash matni:</label>
                                <textarea name="ask_phone" rows="3" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm">{settings.get('ask_phone', '')}</textarea>
                                <p class="text-xs text-slate-400 mt-1">Eslatma: Mijozning ismini chiqarish uchun <code class="text-purple-600 font-mono">{{name}}</code> deb yozing.</p>
                            </div>
                            <div>
                                <label class="block text-sm font-semibold text-slate-700 mb-2">3. Yakuniy matn (Havola bilan yuboriladi):</label>
                                <textarea name="final_message" rows="3" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm">{settings.get('final_message', '')}</textarea>
                            </div>
                        </div>

                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-2">4. Asosiy havola (Sayt/Katalog/Kanal):</label>
                            <input type="url" name="default_promo_link" value="{settings.get('default_promo_link', '')}" class="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none text-sm font-mono" placeholder="https://sizning-saytingiz.uz">
                        </div>

                        <div class="flex justify-end pt-2">
                            <button type="submit" class="bg-purple-600 hover:bg-purple-700 text-white font-medium px-6 py-2.5 rounded-xl text-sm shadow-sm transition">
                                💾 Direct Shabloni Saqlash
                            </button>
                        </div>
                    </form>
                </div>

                <!-- 2. HAR BIR VIDEO UCHUN MAXSUS QOIDALAR -->
                <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                    <div class="border-b border-slate-100 pb-4 mb-6">
                        <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                            🎬 2. Har Bir Video (Reels) Uchun Maxsus Qoidalar
                        </h2>
                        <p class="text-sm text-slate-500">Mijoz ma'lum bir videongizga yoki kalit so'zga izoh qoldirganda boshqacha matn va havola yuborish.</p>
                    </div>

                    <!-- Mavjud qoidalar jadvali -->
                    <div class="overflow-x-auto rounded-xl border border-slate-100 mb-8">
                        <table class="w-full text-left text-sm">
                            <thead class="bg-slate-50 text-xs font-semibold uppercase text-slate-500 border-b border-slate-100">
                                <tr>
                                    <th class="px-6 py-3.5">Aksiya / Video Nomi</th>
                                    <th class="px-6 py-3.5">Kalit so'z</th>
                                    <th class="px-6 py-3.5">Izohga javob</th>
                                    <th class="px-6 py-3.5">Beriladigan Havola</th>
                                    <th class="px-6 py-3.5">Amal</th>
                                </tr>
                            </thead>
                            <tbody>
                                {campaigns_html}
                            </tbody>
                        </table>
                    </div>

                    <!-- Yangi qoida qo'shish formasi -->
                    <div class="bg-slate-50 p-6 rounded-2xl border border-slate-200">
                        <h3 class="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4">➕ Yangi Video Qoidasi Qo'shish</h3>
                        <form method="POST" action="/admin/campaign/create" class="space-y-4">
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-xs font-semibold text-slate-700 mb-1">Aksiya yoki Video nomi:</label>
                                    <input type="text" name="name" required class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Masalan: Umra Safari 2026">
                                </div>
                                <div>
                                    <label class="block text-xs font-semibold text-slate-700 mb-1">Trigger Kalit so'z (izohda yoziladigan so'z):</label>
                                    <input type="text" name="trigger_keyword" required class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Masalan: umra (yoki narx, dubay)">
                                </div>
                            </div>

                            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-xs font-semibold text-slate-700 mb-1">Izoh ostiga ommaviy javob:</label>
                                    <input type="text" name="public_reply" required class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Directingizga Umra narxlarini yubordik! 🕋">
                                </div>
                                <div>
                                    <label class="block text-xs font-semibold text-slate-700 mb-1">Mijozga beriladigan maxsus havola:</label>
                                    <input type="url" name="promo_link" required class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm font-mono" placeholder="https://sizning-saytingiz.uz/umra">
                                </div>
                            </div>

                            <div>
                                <label class="block text-xs font-semibold text-slate-700 mb-1">Directga boradigan maxsus xabar:</label>
                                <textarea name="dm_welcome" rows="2" class="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm" placeholder="Salom! Umra safari dasturimiz bilan tanishish uchun ismingizni yozing:"></textarea>
                            </div>

                            <div class="flex justify-end pt-2">
                                <button type="submit" class="bg-slate-900 hover:bg-black text-white font-medium px-5 py-2.5 rounded-xl text-sm transition">
                                    ➕ Qoidani Saqlash
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- 3. YIG'ILGAN LIDLAR (MIJOZLAR) -->
                <div class="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8">
                    <div class="border-b border-slate-100 pb-4 mb-6 flex justify-between items-center">
                        <div>
                            <h2 class="text-lg font-bold text-slate-900 flex items-center gap-2">
                                👥 3. Yig'ilgan Lidlar (Mijozlar Bazasi)
                            </h2>
                            <p class="text-sm text-slate-500">Instagram orqali kelgan barcha mijozlar tarixi.</p>
                        </div>
                        <a href="/api/clients/csv" class="text-sm text-emerald-600 hover:underline font-medium">Excel yuklab olish →</a>
                    </div>

                    <div class="overflow-x-auto rounded-xl border border-slate-100">
                        <table class="w-full text-left text-sm">
                            <thead class="bg-slate-50 text-xs font-semibold uppercase text-slate-500 border-b border-slate-100">
                                <tr>
                                    <th class="px-6 py-3.5">Ism</th>
                                    <th class="px-6 py-3.5">Telefon</th>
                                    <th class="px-6 py-3.5">Yo'nalish / Aksiya</th>
                                    <th class="px-6 py-3.5">Manba</th>
                                    <th class="px-6 py-3.5">Vaqti</th>
                                </tr>
                            </thead>
                            <tbody>
                                {clients_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </main>
    </body>
    </html>
    """
    return html
