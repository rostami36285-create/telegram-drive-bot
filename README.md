# 🤖 Telegram Drive Bot

ربات تلگرامی برای آپلود خودکار فایل به **گوگل درایو شخصی** هر کاربر.  
هر کاربر با حساب Google خودش وارد می‌شود — هیچ فایلی روی سرور ذخیره نمی‌ماند.

---

## ✨ قابلیت‌ها

- 📤 **آپلود فایل** — ارسال فایل مستقیم به ربات → آپلود به Google Drive
- 🔗 **آپلود با لینک** — دادن URL فایل → دانلود + آپلود خودکار
- ☁️ **درایو شخصی** — هر کاربر به حساب Google خودش وصل می‌شود
- 📁 **مدیریت فایل‌ها** — مشاهده، باز کردن و حذف فایل‌های آپلودشده
- 📊 **نمایش فضای درایو** — مصرف و ظرفیت کل نمایش داده می‌شود
- 📢 **کانال اجباری** — محدود کردن دسترسی به عضوهای کانال خاص
- 🛡 **پنل ادمین** — مدیریت کاربران، کانال‌ها، OAuth و آمار
- ⚙️ **مدیریت OAuth از پنل** — تنظیم Client ID/Secret بدون ری‌استارت
- 🔒 **قفل آپلود** — در حین آپلود، دستورات دیگر بلاک می‌شوند
- 📈 **نوار پیشرفت** — درصد دانلود و آپلود در لحظه نمایش داده می‌شود
- ❌ **لغو آپلود** — کاربر می‌تواند آپلود در حال انجام را لغو کند
- 📋 **صف آپلود** — چند آپلود همزمان با مدیریت صف
- 🚦 **ضد اسپم** — محدودیت درخواست و سقف روزانه آپلود

---

## 📋 پیش‌نیازها

- سرور لینوکسی (Ubuntu 20.04+ / Debian 11+ / CentOS 8+)
- یک **دامنه** که DNS آن به IP سرور اشاره کند
- Python 3.10+
- حساب Google Cloud با Drive API فعال

---

## 🚀 نصب سریع (یک دستور)

```bash
curl -fsSL https://raw.githubusercontent.com/rostami36285-create/telegram-drive-bot/main/install.sh | sudo bash
```

اسکریپت به‌صورت تعاملی موارد زیر را می‌پرسد:
1. **Bot Token** — از [@BotFather](https://t.me/BotFather) بگیرید
2. **Admin ID** — از [@userinfobot](https://t.me/userinfobot) بگیرید
3. **دامنه** — مثال: `bot.example.com`

سپس به‌صورت خودکار:
- Python venv + وابستگی‌ها نصب می‌شود
- Nginx پیکربندی می‌شود
- SSL رایگان از Let's Encrypt دریافت می‌شود
- Webhook تلگرام ثبت می‌شود
- سرویس systemd ساخته و فعال می‌شود

---

## ⚙️ تنظیم Google Drive API

بعد از نصب، برای فعال کردن آپلود به Drive:

### ۱. ساخت پروژه در Google Cloud
1. به [console.cloud.google.com](https://console.cloud.google.com) بروید
2. پروژه جدید بسازید
3. **APIs & Services → Library** → `Google Drive API` → **Enable**

### ۲. ساخت OAuth Credentials
1. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
2. نوع: **Web application**
3. در **Authorized redirect URIs** اضافه کنید:
   ```
   https://YOUR_DOMAIN/oauth/callback
   ```
4. **Client ID** و **Client Secret** را کپی کنید

### ۳. وارد کردن در پنل ادمین (بدون ری‌استارت)
در تلگرام:
```
/admin → ⚙️ تنظیمات OAuth گوگل → تنظیم Client ID → تنظیم Client Secret → 🧪 تست اتصال
```

---

## 🛡 پنل ادمین

دستور `/admin` پنل مدیریت را باز می‌کند:

| گزینه | توضیح |
|-------|-------|
| 🔍 جستجوی کاربر | جستجو با ID یا یوزرنیم |
| 👥 لیست کاربران | نمایش همه کاربران با صفحه‌بندی |
| 📢 مدیریت کانال‌ها | اضافه/حذف کانال اجباری |
| ⚙️ تنظیمات OAuth | تنظیم و تست Google Credentials |
| 📊 آمار کلی | تعداد کاربران ثبت‌شده |

---

## 📱 دستورات کاربران

| دستور | توضیح |
|-------|-------|
| `/start` | شروع و منوی اصلی |
| `/admin` | پنل مدیریت (فقط ادمین) |

---

## 🔄 به‌روزرسانی

```bash
sudo bash /opt/telegram-drive-bot/install.sh
```

---

## 🔧 مدیریت سرویس

```bash
# وضعیت
sudo systemctl status telegram-drive-bot

# ری‌استارت
sudo systemctl restart telegram-drive-bot

# لاگ زنده
sudo journalctl -u telegram-drive-bot -f

# بررسی سلامت
curl https://YOUR_DOMAIN/health

# تست تمدید SSL
certbot renew --dry-run
```

---

## 📁 ساختار پروژه

```
telegram-drive-bot/
├── main.py              # نقطه ورود — FastAPI + webhook
├── config.py            # تنظیمات از .env
├── install.sh           # نصب‌کننده خودکار
├── requirements.txt
├── bot/
│   ├── handlers/        # هندلرهای تلگرام
│   ├── keyboards.py     # کیبردهای inline
│   ├── states.py        # وضعیت‌های مکالمه
│   └── rate_limiter.py  # ضد اسپم
├── database/
│   ├── db.py            # عملیات SQLite
│   └── encryption.py    # رمزنگاری Fernet
├── services/
│   ├── auth.py          # Google OAuth
│   ├── drive.py         # آپلود/دانلود/حذف Drive
│   └── queue.py         # صف آپلود
└── oauth/
    └── server.py        # روت‌های FastAPI
```

---

## 🔒 امنیت

- توکن‌های Google OAuth هر کاربر با **Fernet** رمزنگاری می‌شوند
- Webhook با `X-Telegram-Bot-Api-Secret-Token` تأیید می‌شود
- سرور روی `127.0.0.1` باند است — فقط Nginx دسترسی دارد
- HSTS و TLS 1.2/1.3 فعال است

---

## 📄 لایسنس

MIT License