# 🚀 Instagram Direct Avtomatlashtirish & Lidlar Bazasi Tizimi

Ushbu loyiha Instagram Direct xabarlarini to'liq avtomatlashtirish, mijozlarga havolalar ulashish va ularning ma'lumotlarini (ism, telefon raqam) bazaga saqlash uchun mo'ljallangan mustaqil, tekin va xavfsiz (Meta Graph API asosida) backend tizimidir.

---

## 📌 Asosiy Imkoniyatlari:
1. **Direct Avtomatik Javob:** Kalit so'zlar (`salom`, `kurs`, `narx`, `link`, `katalog` va h.k.) yozilganda zudlik bilan javob beradi.
2. **Mijozlar Bazasini Yig'ish:** Havolani berishdan oldin mijozning ismi va telefon raqamini bosqichma-bosqich qabul qiladi.
3. **Havola va Tugma Taqdim Etish:** Ro'yxatdan o'tgan mijozga sizning havolangizni (sayt, bot, katalog yoki to'lov) chiroyli tugma/matn shaklida yetkazadi.
4. **Mijozlar Bazasini Saqlash:** Ma'lumotlar avtomatik `data/clients.db` (SQLite) faylida to'planadi.
5. **Excel / CSV formatida yuklab olish:** Istalgan vaqtda brauzerdan `http://server-ip:8000/api/clients/csv` orqali bazani Excelga ko'chirib olish mumkin.
6. **Telegram Admin Bildirishnomalari (Ixtiyoriy):** Har bir yangi mijoz telefon qoldirganda shaxsiy Telegramingizga zudlik bilan bildirishnoma boradi.
7. **Serverga oson ko'chirish:** Docker va Docker Compose to'liq sozlangan.

---

## 🛠 1. Lokal Kompyuterda Sinab Ko'rish

### A. Kerakli paketlarni o'rnatish
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### B. Sozlamalarni kiritish
`.env` faylini ochib, kerakli qiymatlarni kiriting:
* `PAGE_ACCESS_TOKEN` = Meta Developer'dan olingan token
* `VERIFY_TOKEN` = Masalan, `mening_maxfiy_webhook_tokenim_123`
* `PROMO_LINK` = Mijozlarga bermoqchi bo'lgan havolangiz

### C. Serverni yoqish
```bash
uvicorn main:app --reload --port 8000
```

### D. Ngrok orqali tashqi internetga ulash (Test uchun)
```bash
ngrok http 8000
```
Ngrok bergan HTTPS havolani oling (masalan: `https://abcd-123.ngrok-free.app`).

---

## ⚙️ 2. Meta (Facebook Developers) Sozlamalari

1. [developers.facebook.com](https://developers.facebook.com) ga kiring -> Ilovangizni tanlang.
2. Chap menyudan **Instagram Graph API** / **Webhooks** bo'limiga kiring:
   * **Callback URL:** `https://abcd-123.ngrok-free.app/webhook` (Serverga ko'chirganda: `https://sizning-domeningiz.uz/webhook`)
   * **Verify Token:** `.env` dagi qiymat (masalan: `mening_maxfiy_webhook_tokenim_123`)
3. **Obunalar (Subscriptions) juda muhim:**
   * `messages` (Direct xabarlar uchun)
   * `messaging_postbacks` (Tugmalar uchun)
   * `comments` (Videolardagi izohlarni tutish uchun!)
4. **Instagram ilovangizda:**
   * Sozlamalar -> *Messages and story replies* -> *Message controls* -> **"Allow access to messages"** yoqilganligiga ishonch hosil qiling!

---

## 🤖 3. Telegram Botga Lid Yuborishni Yoqish

1. Telegramda `@BotFather` ga kiring va `/newbot` buyrug'i bilan yangi bot ochib, uning **Tokenini** oling.
2. O'zingizning Telegram ID'ingizni bilish uchun `@userinfobot` ga start bosing (masalan: `123456789`).
   *(Agar lidlar Telegram guruhga tushishi kerak bo'lsa, botni guruhga qo'shib, guruh ID sini yozasiz).*
3. `.env` fayliga kiriting:
   ```env
   TELEGRAM_BOT_TOKEN=bot_tokeningiz
   TELEGRAM_ADMIN_CHAT_ID=chat_idingiz
   ```
4. Endi har safar mijoz video ostiga yoki directga yozib, telefonini qoldirganda Telegramingizga bir zumda xabar va qo'ng'iroq qilish tugmasi keladi!

---

## 🚢 3. Haqiqiy Serverga (VPS/VDS) Ko'chirish

Serveringizga ushbu papkani ko'chirib o'tkazgach, Docker orqali birgina buyruq bilan 24/7 rejimda ishga tushirasiz:

```bash
# 1. Serverda papkaga kiring
cd instagram-automation

# 2. Docker orqali fonda ishga tushirish
docker compose up -d --build
```

Loglarni tekshirish uchun:
```bash
docker compose logs -f
```

Tizimni to'xtatish uchun:
```bash
docker compose down
```

---

## 📊 4. Mijozlar Bazasini Ko'rish

* Brauzerda API hujjatlari: `http://localhost:8000/docs`
* JSON formatda mijozlar ro'yxati: `http://localhost:8000/api/clients`
* Excel/CSV formatda bazani yuklab olish: `http://localhost:8000/api/clients/csv`
