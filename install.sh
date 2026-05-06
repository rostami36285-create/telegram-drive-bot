#!/usr/bin/env bash
# ============================================================
#  Telegram Drive Bot — نصب‌کننده یک‌خطی برای سرورهای لینوکس
#
#  ⚠️  این ربات فقط با دامنه + SSL کار می‌کند (webhook-only)
#
#  نصب تازه:
#    curl -fsSL https://raw.githubusercontent.com/rostami36285-create/telegram-drive-bot/main/install.sh | sudo bash
#
#  به‌روزرسانی:
#    sudo bash /opt/telegram-drive-bot/install.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[•]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗] $*${NC}" >&2; exit 1; }
hr()      { echo -e "${CYAN}──────────────────────────────────────────────${NC}"; }

INSTALL_DIR="${INSTALL_DIR:-/opt/telegram-drive-bot}"
SERVICE="telegram-drive-bot"
REPO_URL="https://github.com/rostami36285-create/telegram-drive-bot.git"
BOT_USER="drivebot"

# ── Root check ────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && die "با sudo اجرا کنید."

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   🤖 Telegram Drive Bot — Installer          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── تضمین دسترسی به ترمینال — حتی در curl | bash ─────────────
# وقتی اسکریپت از پایپ اجرا می‌شه stdin = لوله curl نه ترمینال
# با باز کردن /dev/tty روی fd 3 مشکل حل می‌شه
if [[ -t 0 ]]; then
    exec 3<&0                   # stdin خودش ترمینال است
elif [[ -e /dev/tty ]]; then
    exec 3</dev/tty             # /dev/tty را برای ورودی کاربر باز می‌کنیم
else
    die "ترمینال تعاملی یافت نشد.\nاسکریپت را مستقیماً اجرا کنید: sudo bash install.sh"
fi

# ── شناسایی توزیع ────────────────────────────────────────────
[[ -f /etc/os-release ]] && . /etc/os-release || die "توزیع شناخته نشد."
info "سیستم‌عامل: ${PRETTY_NAME:-$ID}"

# ── تابع نصب پکیج ───────────────────────────────────────────
pkg_install() {
  case "${ID:-}" in
    ubuntu|debian) apt-get install -y -qq "$@" 2>/dev/null ;;
    centos|rhel|rocky|almalinux|fedora)
      command -v dnf &>/dev/null && dnf install -y "$@" 2>/dev/null \
                                 || yum install -y "$@" 2>/dev/null ;;
    arch) pacman -Sy --noconfirm "$@" 2>/dev/null ;;
    *) warn "توزیع ناشناخته — پکیج‌ها را دستی نصب کنید."; return 0 ;;
  esac
}

# ── به‌روزرسانی امن فایل .env (بدون sed و مشکل کاراکتر خاص) ──
_env_set() {
  local key="$1" val="$2"
  local tmp; tmp=$(mktemp)
  grep -v "^${key}=" "$ENV" 2>/dev/null > "$tmp" || true
  echo "${key}=${val}" >> "$tmp"
  mv "$tmp" "$ENV"
}

# ── پیش‌نیازهای پایه ─────────────────────────────────────────
info "نصب پیش‌نیازها..."
case "${ID:-}" in ubuntu|debian) apt-get update -qq ;; esac
pkg_install python3 python3-pip python3-venv git curl openssl
success "پیش‌نیازها نصب شد."

# ── بررسی Python 3.10+ ───────────────────────────────────────
PY=$(command -v python3 || die "Python یافت نشد.")
$PY -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" \
  || die "Python 3.10+ لازم است. نسخه فعلی: $($PY --version)"
success "Python: $($PY --version)"

# ── Clone / آپدیت کد ─────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "به‌روزرسانی کد در $INSTALL_DIR ..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  info "دریافت کد از GitHub..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
success "کد آماده است."

# ── محیط مجازی + وابستگی‌ها ──────────────────────────────────
VENV="$INSTALL_DIR/venv"
info "ساخت محیط مجازی Python..."
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
success "وابستگی‌های Python نصب شد."

# ── فایل .env ─────────────────────────────────────────────────
ENV="$INSTALL_DIR/.env"
[[ -f "$ENV" ]] || cp "$INSTALL_DIR/.env.example" "$ENV"

# ══════════════════════════════════════════════════════════════
#  پیکربندی تعاملی — فقط در نصب اول (وقتی token هنوز placeholder است)
# ══════════════════════════════════════════════════════════════
if grep -q "your_telegram_bot_token_here" "$ENV" 2>/dev/null; then
  hr
  echo -e "${BOLD}  پیکربندی ربات (نصب اول)${NC}"
  hr

  echo -en "${BOLD}  📱 Telegram Bot Token: ${NC}"
  read -r TG_TOKEN <&3
  [[ -n "$TG_TOKEN" ]] && _env_set "TELEGRAM_BOT_TOKEN" "$TG_TOKEN"

  echo -en "${BOLD}  👤 Admin Telegram ID(s) (با کاما — از @userinfobot بگیرید): ${NC}"
  read -r ADMINS <&3
  [[ -n "$ADMINS" ]] && _env_set "ADMIN_IDS" "$ADMINS"

  echo -en "${BOLD}  📢 کانال‌های اجباری (اختیاری، مثال: @ch1,@ch2): ${NC}"
  read -r CHANNELS <&3
  [[ -n "$CHANNELS" ]] && _env_set "REQUIRED_CHANNELS" "$CHANNELS"
fi

# ── کلید رمزنگاری — در هر صورت بررسی و ایجاد می‌شود ──────────
if grep -q "your_fernet_key_here" "$ENV" 2>/dev/null; then
  ENC_KEY=$("$VENV/bin/python3" -c \
    "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  _env_set "ENCRYPTION_KEY" "$ENC_KEY"
  success "کلید رمزنگاری ایجاد شد."
fi

# ══════════════════════════════════════════════════════════════
#  دامنه — همیشه می‌پرسیم (با پیش‌فرض دامنه فعلی برای به‌روزرسانی)
# ══════════════════════════════════════════════════════════════
DOMAIN=""
_current_domain=$(grep "^WEBHOOK_URL=https://" "$ENV" 2>/dev/null \
  | sed 's|WEBHOOK_URL=https://||' || true)

hr
echo -e "${BOLD}  دامنه سرور — الزامی${NC}"
echo "  ربات فقط با HTTPS/webhook کار می‌کند."
echo "  مطمئن شوید DNS دامنه به IP این سرور اشاره می‌کند."
[[ -n "$_current_domain" ]] && \
  echo -e "  دامنه فعلی: ${CYAN}$_current_domain${NC}"
hr

while [[ -z "$DOMAIN" ]]; do
  if [[ -n "$_current_domain" ]]; then
    echo -en "${BOLD}  🌐 دامنه [Enter برای نگه‌داشتن «${_current_domain}»]: ${NC}"
    read -r _inp <&3
    DOMAIN="${_inp:-$_current_domain}"
  else
    echo -en "${BOLD}  🌐 دامنه (مثال: bot.example.com): ${NC}"
    read -r DOMAIN <&3
    [[ -z "$DOMAIN" ]] && warn "دامنه اجباری است — بدون دامنه نصب ممکن نیست."
  fi
done

info "دامنه: $DOMAIN"

# ══════════════════════════════════════════════════════════════
#  Nginx + SSL
# ══════════════════════════════════════════════════════════════
info "نصب Nginx و Certbot..."
case "${ID:-}" in
  ubuntu|debian) pkg_install nginx certbot python3-certbot-nginx ;;
  centos|rhel|rocky|almalinux|fedora) pkg_install epel-release nginx certbot python3-certbot-nginx ;;
  arch) pkg_install nginx certbot certbot-nginx ;;
esac
systemctl enable --now nginx
success "Nginx راه‌اندازی شد."

rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# ── تعیین مسیر کانفیگ Nginx (Debian/Ubuntu vs RHEL/CentOS) ───
if [[ -d /etc/nginx/sites-available ]]; then
  NGINX_CONF="/etc/nginx/sites-available/${SERVICE}"
  NGINX_LINK="/etc/nginx/sites-enabled/${SERVICE}"
else
  NGINX_CONF="/etc/nginx/conf.d/${SERVICE}.conf"
  NGINX_LINK=""
fi

# ── کانفیگ HTTP موقت برای تأیید Let's Encrypt ────────────────
cat > "$NGINX_CONF" <<NGINXEOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    root /var/www/html;
    location /.well-known/acme-challenge/ { try_files \$uri =404; }
    location / { return 301 https://\$host\$request_uri; }
}
NGINXEOF

[[ -n "$NGINX_LINK" ]] && ln -sf "$NGINX_CONF" "$NGINX_LINK"
nginx -t && systemctl reload nginx

# ── گواهی SSL با Let's Encrypt ────────────────────────────────
info "دریافت گواهی SSL برای $DOMAIN ..."
certbot certonly \
  --nginx \
  -d "$DOMAIN" \
  --non-interactive \
  --agree-tos \
  --email "admin@${DOMAIN}" \
  2>&1 || die "SSL شکست خورد.\n  ← مطمئن شوید DNS دامنه «${DOMAIN}» به IP این سرور اشاره دارد.\n  ← پورت 80 باید باز باشد."
success "گواهی SSL دریافت شد."

# ── کانفیگ HTTPS کامل Nginx ──────────────────────────────────
cat > "$NGINX_CONF" <<NGINXEOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_stapling        on;
    ssl_stapling_verify on;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 0;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 600s;
        proxy_connect_timeout 10s;
    }
}
NGINXEOF

nginx -t && systemctl reload nginx
success "Nginx با HTTPS پیکربندی شد."

# ── به‌روزرسانی .env ──────────────────────────────────────────
WH_SECRET=$(openssl rand -hex 32)
_env_set "WEBHOOK_URL"        "https://${DOMAIN}"
_env_set "WEBHOOK_SECRET"     "${WH_SECRET}"
_env_set "OAUTH_REDIRECT_URI" "https://${DOMAIN}/oauth/callback"
_env_set "SERVER_HOST"        "127.0.0.1"
success ".env با تنظیمات دامنه به‌روز شد."

# ── تمدید خودکار SSL ─────────────────────────────────────────
if systemctl list-timers --all 2>/dev/null | grep -q certbot; then
  success "تمدید خودکار SSL فعال است (certbot.timer)."
else
  (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") \
    | sort -u | crontab -
  success "تمدید SSL از طریق cron تنظیم شد."
fi
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
cat > /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh <<'HOOKEOF'
#!/bin/bash
systemctl reload nginx
HOOKEOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh

# ══════════════════════════════════════════════════════════════
#  کاربر سیستمی + سرویس systemd
# ══════════════════════════════════════════════════════════════
NOLOGIN=$(command -v nologin 2>/dev/null || echo /sbin/nologin)
id "$BOT_USER" &>/dev/null || \
  useradd --system --no-create-home --shell "$NOLOGIN" "$BOT_USER"
chown -R "$BOT_USER:$BOT_USER" "$INSTALL_DIR"
chmod 600 "$ENV"

cat > "/etc/systemd/system/${SERVICE}.service" <<SVCEOF
[Unit]
Description=Telegram Drive Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${BOT_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV}
ExecStart=${VENV}/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable "$SERVICE"
success "سرویس systemd ثبت شد."

# ══════════════════════════════════════════════════════════════
#  راه‌اندازی + ثبت Webhook
# ══════════════════════════════════════════════════════════════
TG_TOKEN_LIVE=$(grep "^TELEGRAM_BOT_TOKEN=" "$ENV" | cut -d'=' -f2- || true)

if [[ -z "$TG_TOKEN_LIVE" ]] || \
   echo "$TG_TOKEN_LIVE" | grep -q "your_telegram_bot_token_here"; then
  warn "Telegram Token هنوز تنظیم نشده — سرویس شروع نمی‌شود."
  warn "  → sudo nano $ENV"
  warn "  → sudo systemctl start $SERVICE"
else
  systemctl restart "$SERVICE"
  success "سرویس ربات راه‌اندازی شد."

  # ── ثبت Webhook مستقیم از طریق Telegram API ──────────────
  # نیازی به بالا بودن ربات نیست — Nginx+SSL کافی است
  info "ثبت Webhook در تلگرام (۳ ثانیه صبر می‌کنیم)..."
  sleep 3

  WH_RESULT=$(curl -sf --connect-timeout 15 \
    "https://api.telegram.org/bot${TG_TOKEN_LIVE}/setWebhook" \
    --data-urlencode "url=https://${DOMAIN}/webhook/${TG_TOKEN_LIVE}" \
    --data-urlencode "secret_token=${WH_SECRET}" \
    -d "drop_pending_updates=true" \
    -d 'allowed_updates=["message","callback_query","chat_member"]' \
    2>&1 || echo '{"ok":false,"description":"curl timeout"}')

  if echo "$WH_RESULT" | grep -q '"ok":true'; then
    success "Webhook تلگرام ثبت شد ✓"
  else
    warn "نتیجه ثبت webhook: $WH_RESULT"
    warn "برای ثبت دستی:"
    warn "  curl 'https://api.telegram.org/bot${TG_TOKEN_LIVE}/setWebhook' \\"
    warn "    --data-urlencode 'url=https://${DOMAIN}/webhook/${TG_TOKEN_LIVE}'"
  fi

  # ── بررسی سلامت ربات ────────────────────────────────────
  info "بررسی سلامت ربات..."
  READY=0
  for _i in $(seq 1 15); do
    curl -sf "http://127.0.0.1:8080/health" > /dev/null 2>&1 && READY=1 && break
    sleep 2
  done
  if [[ $READY -eq 1 ]]; then
    success "ربات فعال و پاسخگوست ✓"
  else
    warn "ربات هنوز آماده نشده — لاگ را بررسی کنید:"
    warn "  sudo journalctl -u $SERVICE -n 50 --no-pager"
  fi
fi

# ══════════════════════════════════════════════════════════════
#  خلاصه نهایی
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ نصب با موفقیت انجام شد!                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
printf "  %-28s %s\n" "مسیر نصب:"      "$INSTALL_DIR"
printf "  %-28s %s\n" "فایل تنظیمات:" "$ENV"
printf "  %-28s %s\n" "آدرس:"          "https://${DOMAIN}"
echo ""
echo -e "  ${YELLOW}⚠️  مرحله باقی‌مانده — Google Drive API:${NC}"
echo ""
echo "  ۱. https://console.cloud.google.com → پروژه جدید"
echo "  ۲. APIs & Services → Google Drive API → Enable"
echo "  ۳. Credentials → OAuth 2.0 Client ID (Web application)"
echo -e "  ۴. Redirect URI: ${CYAN}https://${DOMAIN}/oauth/callback${NC}"
echo "  ۵. در ربات:"
echo -e "     ${CYAN}/admin → ⚙️ تنظیمات OAuth گوگل${NC}"
echo ""
hr
echo "  دستورات مدیریت:"
echo -e "  ${CYAN}sudo systemctl restart $SERVICE${NC}"
echo -e "  ${CYAN}sudo journalctl -u $SERVICE -f${NC}"
echo -e "  ${CYAN}curl https://${DOMAIN}/health${NC}"
echo -e "  ${CYAN}sudo bash $INSTALL_DIR/install.sh${NC}  ← به‌روزرسانی"
echo ""