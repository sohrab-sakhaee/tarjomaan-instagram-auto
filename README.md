# 🚀 سیستم اتوماتیک اینستاگرام - Tarjomaan

سیستم خودکار برای:
- ✅ دریافت مقالات
- ✅ ترجمه و خلاصه‌سازی عامیانه
- ✅ تولید عکس با Flux
- ✅ پست‌کردن در اینستاگرام

---

## 📋 نیازمندی‌ها

- GitHub Account
- Railway Account
- Groq API Key
- Replicate Token
- اینستاگرام Account

---

## ⚙️ نصب

### 1️⃣ GitHub Setup

```bash
# Fork این repo یا کلون کن
git clone https://github.com/sohrab-sakhaee/tarjomaan-instagram-auto.git
cd tarjomaan-instagram-auto
```

### 2️⃣ Railway Setup

1. برو: https://railway.app
2. Sign up (GitHub)
3. New Project → Deploy from GitHub
4. Repo رو انتخاب کن

### 3️⃣ Environment Variables

توی Railway:

```
GROQ_API_KEY=gsk_YOUR_KEY
REPLICATE_TOKEN=r8_YOUR_TOKEN
INSTAGRAM_USERNAME=articlecopier
INSTAGRAM_PASSWORD=YOUR_PASSWORD
FEED_URL=https://tarjomaan.com/feed
```

### 4️⃣ Deploy

```
Railway خودکار deploy می‌کند!
```

---

## 📅 شدول (Schedule)

هر روز ساعت **9 صبح** اجرا می‌شود.

برای تغییر:
- `app.py` رو ویرایش کن
- کد `schedule` رو تغییر بده

---

## 📊 نتایج

نتایج در `results.json` ذخیره می‌شوند:

```json
[
  {
    "timestamp": "2024-01-15T09:00:00",
    "title": "عنوان مقاله",
    "summary": "خلاصه...",
    "image_url": "https://..."
  }
]
```

---

## 🐛 مشکلات

### Instagram بدون پست (بدون VPN)

اگر در ایران هستی و Instagram مسدود است:
- VPN فعال کن
- یا متن + عکس رو دستی پست کن

### Timeout

اگر Flux خیلی طول کشید:
- دوباره deploy کن
- یا `num_inference_steps` رو کم کن

---

## 📞 پشتیبانی

اگر مشکل داری:
1. لاگ‌ها رو چک کن (Railway → Logs)
2. API Keys رو دوبارهچک کن
3. VPN رو فعال کن

---

## 📜 License

MIT
