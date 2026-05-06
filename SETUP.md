# راهنمای راه‌اندازی ربات تلگرام — آپلودر گوگل درایو

## مرحله ۱ — ساخت ربات تلگرام

1. به [@BotFather](https://t.me/BotFather) در تلگرام پیام دهید
2. دستور `/newbot` را بفرستید
3. نام و نام کاربری ربات را وارد کنید
4. **Token** دریافتی را کپی کنید

---

## مرحله ۲ — ساخت پروژه Google Cloud

1. به [Google Cloud Console](https://console.cloud.google.com) بروید
2. یک پروژه جدید بسازید
3. در منو به **APIs & Services → Library** بروید
4. **Google Drive API** را جستجو کرده و فعال کنید
5. به **APIs & Services → Credentials** بروید
6. روی **Create Credentials → OAuth client ID** کلیک کنید
7. نوع Application را **Web application** انتخاب کنید
8. در بخش **Authorized redirect URIs** آدرس زیر را اضافه کنید:
   - برای تست محلی: `http://localhost:8080/oauth/callback`
   - برای سرور: `https://yourdomain.com/oauth/callback`
9. **Client ID** و **Client Secret** را کپی کنید

> ⚠️ در **OAuth consent screen** باید app را به حالت **External** تنظیم کرده و
> ایمیل کاربرانی که می‌خواهند از ربات استفاده کنند را در **Test users** اضافه کنید
> (تا زمانی که app تأیید نشده).

---

## مرحله ۳ — نصب و پیکربندی

```bash
cd telegram-drive-bot

# ساخت محیط مجازی
python3 -m venv venv
source venv/bin/activate

# نصب وابستگی‌ها
pip install -r requirements.txt

# ساخت فایل تنظیمات
cp .env.example .env
# فایل .env را ویرایش کنید و مقادیر واقعی را وارد کنید
nano .env
```

---

## مرحله ۴ — اجرا

```bash
python main.py
```

ربات شروع به polling می‌کند و وب‌سرور OAuth روی پورت ۸۰۸۰ اجرا می‌شود.

---

## استفاده

| دستور | توضیح |
|-------|-------|
| `/start` | پیام خوش‌آمد |
| `/auth` | اتصال به گوگل درایو (اولین بار) |
| `/status` | بررسی وضعیت اتصال |
| `/disconnect` | قطع اتصال |
| ارسال لینک | دانلود و آپلود خودکار به Drive |

---

## اجرا روی سرور (systemd)

```ini
# /etc/systemd/system/drive-bot.service
[Unit]
Description=Telegram Drive Bot
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/telegram-drive-bot
ExecStart=/path/to/venv/bin/python main.py
Restart=always
EnvironmentFile=/path/to/telegram-drive-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now drive-bot
```

## نکات مهم

- فایل `.env` را هرگز در git قرار ندهید
- برای سرور عمومی حتماً از HTTPS استفاده کنید (Nginx + Certbot)
- حداکثر حجم فایل پیش‌فرض ۵۰۰ مگابایت است (قابل تغییر در `.env`)
- توکن‌های کاربران در فایل `bot.db` (SQLite) ذخیره می‌شوند
