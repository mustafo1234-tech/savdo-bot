# 🎮 Game Account Marketplace Bot

Telegram bot: o'yin akkauntlarini xavfsiz sotish va sotib olish uchun to'liq marketplace.
Aiogram 3, PostgreSQL (SQLAlchemy async), Alembic, Click to'lov webhook va Render deployga tayyor.

## Asosiy imkoniyatlar

- 👤 Foydalanuvchi profili, balans, reyting, qoidalar va profil roziligi
- 🔐 Profil maxfiyligi: ism/username faqat rozilik bilan bitim ishtirokchilariga ko'rinadi
- 🛒 Akkaunt sotish: rasm, platforma, level, narx, tavsif, kontakt
- 🔎 Qidiruv, platforma bo'yicha filtrlash, sahifalash, ko'rishlar soni
- 🔐 Xavfsiz bitim: `PENDING → VERIFYING → SUCCESS`, akkaunt `RESERVED/SOLD`
- 💳 To'lov: ichki balans yoki Click (webhook orqali tasdiqlash)
- ⭐ Sotuvchi va xaridor uchun sharh/reyting
- ⚠️ Nizo (dispute): dalil (rasm) bilan admin ko'rigi
- 🛡 Admin panel: statistika, foydalanuvchilar, akkaunt moderatsiyasi,
  to'lovlar/refund, tranzaksiyalar, nizolar, broadcast, sozlamalar
- 🚦 Rate limiting, ban, texnik xizmat rejimi, qoidalar darvozasi

## Texnologiyalar

| Qism | Texnologiya |
|------|-------------|
| Bot | aiogram 3.x (async) |
| DB | PostgreSQL + SQLAlchemy 2.x (asyncpg) |
| Migratsiyalar | Alembic (psycopg2) |
| Webhook | aiohttp |
| Shifrlash | cryptography (Fernet) |
| Deploy | Render (`render.yaml`) |

## Tez boshlash (lokal)

```powershell
# 1) Virtual muhit
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2) Kutubxonalar
pip install -r requirements.txt

# 3) Sozlamalar
Copy-Item .env.example .env
# .env ni tahrirlang: BOT_TOKEN, OWNER_ID, DATABASE_URL, SECRET_KEY

# 4) Baza yaratish (PostgreSQL)
#    CREATE DATABASE game_marketplace;
#    yoki: createdb game_marketplace

# 5) Jadvallar
alembic upgrade head
# yoki .env da AUTO_CREATE_TABLES=true qoldirilsa, bot o'zi yaratadi

# 6) Ishga tushirish
python main.py
```

Bot ishga tushgach: `/start` → qoidalar → profil roziligi → asosiy menyu. Admin: `/admin`.

> `AUTO_CREATE_TABLES=true` faqat birinchi ishga tushirish uchun qulay.
> Katta loyihada `alembic upgrade head` ishlatib, keyin uni `false` qiling.
> Eski bazada yangi ustunlar yetishmasa (masalan `profile_consent`), bot ishga
> tushganda ularni avtomatik qo'shadi. Baribir `alembic upgrade head` tavsiya etiladi.

## Muhit o'zgaruvchilari

To'liq ro'yxat `.env.example` da. Majburiy:

| O'zgaruvchi | Tavsif |
|-------------|--------|
| `BOT_TOKEN` | @BotFather tokeni |
| `OWNER_ID` | Admin Telegram ID (raqam) |
| `DATABASE_URL` | PostgreSQL URL (`postgres://` ham qabul qilinadi) |
| `SECRET_KEY` yoki `ENCRYPTION_KEY` | Shifrlash kaliti (o'zgartirmang!) |

Muhim ixtiyoriylar:

| O'zgaruvchi | Default | Tavsif |
|-------------|---------|--------|
| `AUTO_CREATE_TABLES` | `true` | Jadvallarni avtomatik yaratish |
| `DEFAULT_COMMISSION` | `10` | Komissiya % (sotuvchi summasidan ushlanadi) |
| `DEFAULT_MIN_PRICE` | `5000` | Minimal narx |
| `DEFAULT_SUPPORT` | `@support` | Qo'llab-quvvatlash kontakti |
| `PUBLIC_BASE_URL` | — | Click webhook uchun HTTPS manzil |
| `PORT`, `WEB_HOST` | `8080`, `0.0.0.0` | Web server |
| `THROTTLE_LIMIT`, `THROTTLE_WINDOW` | `8`, `3` | Rate limit |
| `CLICK_SERVICE_ID/MERCHANT_ID/SECRET_KEY` | — | Click to'lov (uchtasi birga) |

## Click to'lovni ulash

1. Click merchant kabinetida xizmat yarating.
2. `.env` ga `CLICK_SERVICE_ID`, `CLICK_MERCHANT_ID`, `CLICK_SECRET_KEY` ni yozing.
3. `PUBLIC_BASE_URL=https://<domeningiz>` (oxirida `/` yo'q) qo'ying.
4. Click kabinetida webhook URL:
   - Tavsiya: `https://<domeningiz>/click/callback` (action asosida)
   - Yoki alohida: `/click/prepare` va `/click/complete`
5. Server HTTPS bo'lishi shart. `GET /health` orqali tirikligini tekshirish mumkin.

To'lov mantiqi:

- `deal:pay_click` → payment yaratiladi va Click URL qaytariladi
- Click `prepare` → summa/akkaunt tekshiriladi, payment `PENDING`
- Click `complete` → imzo tekshiriladi, payment `PAID`, tranzaksiya `VERIFYING`
- Takroriy callbacklar idempotent (ikki marta pul yechilmaydi)
- Balansdan to'lovda ham tranzaksiya `VERIFYING` ga o'tadi
- Xaridor «Akkauntni oldim» tugmasini bosganda tranzaksiya `SUCCESS`, akkaunt `SOLD`,
  sotuvchiga summa (komissiya ayirilgan) tushadi
- Muammo bo'lsa xaridor nizo ochadi; admin xaridor yoki sotuvchi foydasiga hal qiladi

## Admin panel

`/admin` faqat `OWNER_ID` uchun:

- 📊 Statistika: foydalanuvchilar, e'lonlar, tranzaksiyalar, daromad
- 👥 Foydalanuvchilar: ro'yxat, ban/unban, profil
- 🗂 Akkauntlar: tasdiqlash, bloklash, ochish, sotuvchi bilan bog'lanish
- 💳 To'lovlar: ko'rish, qo'lda refund belgilash
- 🔁 Tranzaksiyalar: bekor qilish, nizoni ko'rish
- ⚠️ Nizolar: xaridor/sotuvchi foydasiga hal qilish
- 📢 Broadcast: barcha foydalanuvchilarga xabar
- ⚙️ Sozlamalar: komissiya, min narx, support, texnik xizmat, avto-tasdiq

## Render deploy

1. Reponi GitHub ga yuklang (`.env` yuklanmasin — `.gitignore` tayyor).
2. Render → **New → Blueprint** → reponi tanlang (`render.yaml` avtomatik o'qiladi).
3. Environment bo'limida `sync: false` qiymatlarni kiriting:
   `BOT_TOKEN`, `OWNER_ID`, `DATABASE_URL`, `SECRET_KEY`, Click kalitlari,
   `PUBLIC_BASE_URL`.
4. Deploydan keyin `https://<service>.onrender.com/health` → `{"status":"ok"}`.
5. Click webhookni shu domenga sozlang.

Render `PORT` ni o'zi beradi; `render.yaml` dagi start command: `python main.py`.

## Loyiha tuzilishi

```
bot/
  app.py               # entrypoint: bot, dispatcher, routerlar, web
  config.py            # env config
  constants.py         # platformalar, statuslar, default sozlamalar
  texts.py             # barcha matnlar
  states.py            # FSM holatlari
  web.py               # aiohttp + Click webhook
  database/            # models, session, base
  handlers/            # start, menu, seller, buyer, deals, support, admin
  keyboards/           # inline klaviaturalar
  middlewares/         # database, user, throttling
  services/            # crypto, settings, deals, payments, notifications
  utils/               # formatting, pagination, telegram helpers
alembic/               # migratsiyalar
main.py                # ishga tushirish
render.yaml
requirements.txt
```

## Xavfsizlik

- Bot **hech qachon** akkaunt paroli, email yoki SMS kodini so'ramaydi/saqlaymaydi.
- Akkaunt identifikatori va sotuvchi kontakti Fernet bilan shifrlanadi.
- Kalitlar faqat `.env`/Render Environment da; repoga tushmaydi.
- `SECRET_KEY`/`ENCRYPTION_KEY` ni o'zgartirsangiz, eski shifrlangan ma'lumotlar
  o'qilmaydi — kalitni xavfsiz zaxiralang.
- Admin amallari faqat `OWNER_ID` uchun; rate limit va ban himoyasi mavjud.
- Click imzosi (`md5`) har bir webhookda tekshiriladi; `complete` imzosida
  `merchant_prepare_id` ham hisobga olinadi.
- Profil roziligi berilmagan foydalanuvchi savdo boshlay olmaydi va uning shaxsiy
  ma'lumotlari boshqalarga ko'rsatilmaydi.

## Foydali buyruqlar

```powershell
alembic upgrade head                  # migratsiyalar
alembic revision --autogenerate -m "x"  # yangi migratsiya (dev)
python -m compileall bot              # sintaksis tekshiruv
```

## Muammolar

| Xato | Sabab / yechim |
|------|----------------|
| `ConfigError: BOT_TOKEN...` | `.env` to'ldirilmagan yoki noto'g'ri token |
| `ConfigError: DATABASE_URL...` | URL yo'q yoki noto'g'ri format |
| `ModuleNotFoundError` | `pip install -r requirements.txt` qilinmagan |
| `column users.profile_consent does not exist` | Eski baza; `alembic upgrade head` yoki botni qayta ishga tushiring (avtomatik patch) |
| Click `error: -8` | Server ichki xatosi; loglarni tekshiring |
| Click `error: -1` (sign) | `CLICK_SECRET_KEY` noto'g'ri yoki URL boshqa |
| Webhook 404 | URL `/click/callback` emasligi |
| Render'da web uxlab qolsa | `plan: starter` yoki yuqoriroq reja kerak |
