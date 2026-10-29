# BSB Hisobot Agenti Telegram Boti 🎓

O‘zbekiston umumta’lim maktablari o‘qituvchilari uchun eMaktab elektron jurnali va rasmiy Baholash mezonlari asosida BSB hisoboti (Excel .xlsx) bayonnomalarini avtomatik shakllantiruvchi Telegram Bot.

## Imkoniyatlari:
- 📷 eMaktab jurnali skrinshotidan o‘quvchilar F.I.O va ballarini avtomatik aniqlash (AI Vision).
- 📋 Rasmiy Baholash mezoni PDF skrinshotidan ko‘nikmalar va ballarni ajratib olish.
- 📊 Tayyor A4 Portret shaklda, to‘liq formulalari bilan Excel fayl yaratish.
- ⚡ Gemini API limitlaridan himoyalovchi xavfsiz navbat tizimi va ko‘p kalitli (Multi-key) rotatsiya.

## Loyihani sozlash:
1. `.env.example` faylidan `.env` nusxasini oling.
2. Quyidagi qiymatlarni kiriting:
   - `BOT_TOKEN`: Telegram `@BotFather` dan olingan bot tokeni.
   - `GEMINI_API_KEYS`: Google AI Studio dan olingan Gemini API kalitlari (bir nechta bo'lsa vergul bilan ajrating).
   - `ARCHIVE_CHANNEL_ID`: (Ixtiyoriy) hisobotlar nusxasi tushib turadigan Telegram kanal ID si.

## Railway da 24/7 ishga tushirish:
1. Railway.app saytiga kiring va GitHub orqali kiring.
2. **New Project** -> **Deploy from GitHub repo** -> `agentchb` ni tanlang.
3. **Variables** bo'limiga o'tib, quyidagilarni kiriting:
   - `BOT_TOKEN`
   - `GEMINI_API_KEYS`
4. Deploy avtomatik boshlanadi va bot 24/7 ishlab turadi!
