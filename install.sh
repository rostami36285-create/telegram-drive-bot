#!/usr/bin/env bash
# ============================================================
#  Telegram Drive Bot — نصب‌کننده یک‌خطی برای سرورهای لینوکس
#
#  نصب تازه:
#    curl -fsSL https://raw.githubusercontent.com/rostami36285-create/telegram-drive-bot/main/install.sh | sudo bash
#
#  به‌روزرسانی:
#    sudo bash /opt/telegram-drive-bot/install.sh
# ============================================================
set -euo pipefail

# ── رنگ‌ها ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[•]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗] $*${NC}" >&2; exit 1; }
ask()     { echo -en "${BOLD}${1}${NC} "; }
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

# ── پیش‌نیازهای پایه ─────────────────────────────────────────
info "نصب پیش‌نیازها..."
case "${ID:-}" in
  ubuntu|debian) apt-get update -qq ;;
esac
pkg_install python3 python3-pip python3-venv git curl openssl
success "پیش‌نیازها نصب شد."

# ── بررسی نسخه Python ────────────────────────────────────────
PY=$(command -v python3 || command -v python || die "Python یافت نشد.")
$PY -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" \
  || die "Python 3.10+ لازم است. نسخه فعلی: $($PY --version)"
success "Python: $($PY --version)"

# ── Clone / به‌روزرسانی کد ──────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "به‌روزرسانی کد موجود در $INSTALL_DIR ..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  info "دریافت کد از GitHub..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
success "کد آماده است."

# ── محیط مجازی Python ────────────────────────────────────────
VENV="$INSTALL_DIR/venv"
info "ساخت محیط مجازی Python..."
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
success "وابستگی‌های Python نصب شد."

# ── فایل .env ─────────────────────────────────────────────────
ENV="$INSTALL_DIR/.env"
[[ -f "$ENV" ]] || cp "$INSTALL_DIR/.env.example" "$ENV"

# ── پیکربندی تعاملی ──────────────────────────────────────────
if [[ -t 0 ]] && grep -q "your_telegram_bot_token_here" "$ENV" 2>/dev/null; then
  hr
  echo -e "${BOLD}  پیکربندی ربات${NC}"
  echo "  (Enter = رد کردن)"
  hr

  ask "  📱 Telegram Bot Token:";       read -r TG_TOKEN
  ask "  🔑 Google Client ID:";         read -r G_ID
  ask "  🔒 Google Client Secret:";     read -r G_SECRET
  ask "  👤 Admin Telegram ID(s):";     read -r ADMINS
  ask "  📢 Required Channels (اختیاری):"; read -r CHANNELS

  [[ -n "$TG_TOKEN"  ]] && sed -i "s|your_telegram_bot_token_here|$TG_TOKEN|g"                  "$ENV"
  [[ -n "$G_ID"      ]] && sed -i "s|your_client_id.apps.googleusercontent.com|$G_ID|g"          "$ENV"
  [[ -n "$G_SECRET"  ]] && sed -i "s|your_client_secret|$G_SECRET|g"                              "$ENV"
  [[ -n "$ADMINS"    ]] && sed -i "s|^ADMIN_IDS=.*|ADMIN_IDS=$ADMINS|"                            "$ENV"
  [[ -n "$CHANNELS"  ]] && sed -i "s|^REQUIRED_CHANNELS=.*|REQUIRED_CHANNELS=$CHANNELS|"         "$ENV"

  # کلید رمزنگاری خودکار
  ENC_KEY=$("$VENV/bin/python3" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  sed -i "s|your_fernet_key_here|$ENC_KEY|g" "$ENV"
  success "کلید رمزنگاری ایجاد شد."
fi

# ══════════════════════════════════════════════════════════════
#  راه‌اندازی دامنه + SSL + Nginx + Webhook
# ══════════════════════════════════════════════════════════════
DOMAIN=""
if [[ -t 0 ]]; then
  hr
  echo -e "${BOLD}  تنظیم دامنه و SSL (اختیاری)${NC}"
  echo "  اگر دامنه ندارید Enter بزنید — ربات در حالت polling کار می‌کند."
  hr
  ask "  🌐 دامنه سرور (مثال: bot.example.com):"; read -r DOMAIN
fi

# خواندن token از .env برای استفاده در ثبت webhook
TG_TOKEN_ENV=$(grep "^TELEGRAM_BOT_TOKEN=" "$ENV" | cut -d'=' -f2 || true)

if [[ -n "$DOMAIN" ]]; then

  # ── نصب Nginx + Certbot ──────────────────────────────────
  info "نصب Nginx و Certbot..."
  case "${ID:-}" in
    ubuntu|debian)
      pkg_install nginx certbot python3-certbot-nginx
      ;;
    centos|rhel|rocky|almalinux|fedora)
      pkg_install epel-release nginx certbot python3-certbot-nginx
      ;;
    arch)
      pkg_install nginx certbot certbot-nginx
      ;;
  esac
  systemctl enable --now nginx
  success "Nginx نصب و راه‌اندازی شد."

  # ── حذف سایت پیش‌فرض ─────────────────────────────────────
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

  # ── کانفیگ HTTP موقت برای دریافت گواهی ──────────────────
  NGINX_CONF="/etc/nginx/sites-available/${SERVICE}"
  cat > "$NGINX_CONF" <<NGINXEOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    root /var/www/html;

    location /.well-known/acme-challenge/ {}
    location / { return 301 https://\$host\$request_uri; }
}
NGINXEOF

  [[ -d /etc/nginx/sites-enabled ]] \
    && ln -sf "$NGINX_CONF" "/etc/nginx/sites-enabled/${SERVICE}" \
    || true

  nginx -t && systemctl reload nginx
  info "Nginx با کانفیگ HTTP موقت راه‌اندازی شد."

  # ── دریافت گواهی SSL با Certbot ──────────────────────────
  info "دریافت گواهی SSL از Let's Encrypt برای $DOMAIN ..."
  CERT_EMAIL="admin@${DOMAIN}"
  certbot certonly \
    --nginx \
    -d "$DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "$CERT_EMAIL" \
    --redirect \
    2>&1 || die "دریافت SSL شکست خورد.\n  ← مطمئن شوید DNS دامنه به IP این سرور اشاره می‌کند.\n  ← پورت 80 باز باشد."

  success "گواهی SSL دریافت شد: /etc/letsencrypt/live/${DOMAIN}/"

  # ── کانفیگ HTTPS کامل Nginx ──────────────────────────────
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

    # حداکثر حجم آپلود — برای فایل‌های بزرگ
    client_max_body_size 0;
    proxy_read_timeout   600s;
    proxy_connect_timeout 10s;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
}
NGINXEOF

  nginx -t && systemctl reload nginx
  success "Nginx با HTTPS کامل پیکربندی شد."

  # ── تولید WEBHOOK_SECRET ──────────────────────────────────
  WH_SECRET=$(openssl rand -hex 32)

  # ── به‌روزرسانی .env ──────────────────────────────────────
  # حذف / جایگزینی خطوط مرتبط
  grep -q "^WEBHOOK_URL=" "$ENV" \
    && sed -i "s|^WEBHOOK_URL=.*|WEBHOOK_URL=https://${DOMAIN}|" "$ENV" \
    || echo "WEBHOOK_URL=https://${DOMAIN}" >> "$ENV"

  grep -q "^WEBHOOK_SECRET=" "$ENV" \
    && sed -i "s|^WEBHOOK_SECRET=.*|WEBHOOK_SECRET=${WH_SECRET}|" "$ENV" \
    || echo "WEBHOOK_SECRET=${WH_SECRET}" >> "$ENV"

  # آپدیت OAuth redirect URI
  sed -i "s|^OAUTH_REDIRECT_URI=.*|OAUTH_REDIRECT_URI=https://${DOMAIN}/oauth/callback|" "$ENV"

  # سرور فقط روی loopback
  sed -i "s|^SERVER_HOST=.*|SERVER_HOST=127.0.0.1|" "$ENV"

  success ".env با تنظیمات دامنه به‌روز شد."

  # ── تمدید خودکار SSL ──────────────────────────────────────
  # اطمینان از فعال بودن تایمر certbot
  if systemctl list-timers --all | grep -q certbot; then
    success "تمدید خودکار SSL فعال است (certbot.timer)."
  else
    # fallback: cron job
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") \
      | sort -u | crontab -
    success "تمدید خودکار SSL از طریق cron تنظیم شد (روزانه ۰۳:۰۰)."
  fi

  # هوک reload Nginx پس از تمدید
  mkdir -p /etc/letsencrypt/renewal-hooks/deploy
  cat > /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh <<'HOOKEOF'
#!/bin/bash
systemctl reload nginx
HOOKEOF
  chmod +x /etc/letsencrypt/renewal-hooks/deploy/nginx-reload.sh
  success "هوک reload Nginx پس از تمدید SSL ثبت شد."

  # ── ثبت Webhook در تلگرام ────────────────────────────────
  if [[ -n "$TG_TOKEN_ENV" && "$TG_TOKEN_ENV" != "your_telegram_bot_token_here" ]]; then
    info "ثبت Webhook در تلگرام..."
    WH_RESULT=$(curl -sf \
      "https://api.telegram.org/bot${TG_TOKEN_ENV}/setWebhook" \
      --data-urlencode "url=https://${DOMAIN}/webhook/${TG_TOKEN_ENV}" \
      --data-urlencode "secret_token=${WH_SECRET}" \
      -d "drop_pending_updates=true" \
      -d 'allowed_updates=["message","callback_query","chat_member"]' \
      2>&1 || echo '{"ok":false,"description":"curl failed"}')

    if echo "$WH_RESULT" | grep -q '"ok":true'; then
      success "Webhook تلگرام ثبت شد: https://${DOMAIN}/webhook/***"
    else
      warn "ثبت خودکار webhook شکست خورد. پس از راه‌اندازی ربات دستی اجرا کنید:"
      warn "  curl 'https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://${DOMAIN}/webhook/<TOKEN>'"
    fi
  else
    warn "Token تنظیم نشده — پس از ویرایش .env، webhook را دستی ثبت کنید."
  fi

fi  # end DOMAIN block

# ══════════════════════════════════════════════════════════════
#  کاربر سیستمی + سرویس systemd
# ══════════════════════════════════════════════════════════════

if ! id "$BOT_USER" &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$BOT_USER"
fi
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

# ── راه‌اندازی سرویس ─────────────────────────────────────────
if grep -q "your_telegram_bot_token_here" "$ENV" 2>/dev/null; then
  warn "فایل .env هنوز کامل نشده. سرویس شروع نمی‌شود."
  warn "  → nano $ENV"
  warn "  → sudo systemctl start $SERVICE"
else
  systemctl restart "$SERVICE"
  success "ربات راه‌اندازی شد!"
fi

# ══════════════════════════════════════════════════════════════
#  خلاصه نهایی
# ══════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ نصب با موفقیت انجام شد!                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
printf "  %-24s %s\n" "مسیر نصب:"      "$INSTALL_DIR"
printf "  %-24s %s\n" "فایل تنظیمات:" "$ENV"
[[ -n "$DOMAIN" ]] && printf "  %-24s %s\n" "آدرس سرور:" "https://${DOMAIN}"
echo ""
echo "  دستورات مدیریت:"
echo -e "  ${CYAN}sudo systemctl start   $SERVICE${NC}"
echo -e "  ${CYAN}sudo systemctl stop    $SERVICE${NC}"
echo -e "  ${CYAN}sudo systemctl restart $SERVICE${NC}"
echo -e "  ${CYAN}sudo journalctl -u $SERVICE -f${NC}    ← لاگ زنده"
echo ""
if [[ -n "$DOMAIN" ]]; then
  echo "  بررسی SSL:"
  echo -e "  ${CYAN}certbot certificates${NC}"
  echo -e "  ${CYAN}certbot renew --dry-run${NC}       ← تست تمدید"
  echo ""
  echo "  بررسی Webhook:"
  echo -e "  ${CYAN}curl https://${DOMAIN}/health${NC}"
  echo ""
fi
echo "  به‌روزرسانی:"
echo -e "  ${CYAN}sudo bash $INSTALL_DIR/install.sh${NC}"
echo ""
