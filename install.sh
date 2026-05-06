#!/usr/bin/env bash
# ============================================================
#  Telegram Drive Bot — One-line installer for Linux servers
#
#  Usage (fresh install):
#    curl -fsSL https://raw.githubusercontent.com/rostami36285-create/telegram-drive-bot/main/install.sh | sudo bash
#
#  Update existing install:
#    sudo bash /opt/telegram-drive-bot/install.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[•]${NC} $*"; }
success() { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
die()     { echo -e "${RED}[✗]${NC} $*" >&2; exit 1; }
ask()     { echo -en "${BOLD}${1}${NC} "; }

INSTALL_DIR="${INSTALL_DIR:-/opt/telegram-drive-bot}"
SERVICE="telegram-drive-bot"
REPO_URL="https://github.com/rostami36285-create/telegram-drive-bot.git"

# ── Root check ───────────────────────────────────────────────
[[ $EUID -ne 0 ]] && die "با sudo اجرا کنید: sudo bash install.sh"

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   🤖 Telegram Drive Bot — نصب‌کننده          ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Detect distro ────────────────────────────────────────────
[[ -f /etc/os-release ]] && . /etc/os-release || die "توزیع لینوکس شناخته نشد."
info "سیستم‌عامل: ${PRETTY_NAME:-$ID}"

# ── System packages ───────────────────────────────────────────
info "نصب پیش‌نیازهای سیستم..."
case "${ID:-}" in
  ubuntu|debian)
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv git curl 2>/dev/null
    ;;
  centos|rhel|rocky|almalinux|fedora)
    cmd=$(command -v dnf &>/dev/null && echo dnf || echo yum)
    $cmd install -y python3 python3-pip git curl 2>/dev/null
    ;;
  arch) pacman -Sy --noconfirm python python-pip git curl 2>/dev/null ;;
  *)    warn "توزیع '$ID' ناشناخته — پیش‌نیازها را دستی نصب کنید." ;;
esac
success "پیش‌نیازهای سیستم نصب شد."

# ── Python version check ─────────────────────────────────────
PY=$(command -v python3 || command -v python || die "Python یافت نشد.")
$PY -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" \
  || die "Python 3.10 یا بالاتر لازم است. نسخه فعلی: $($PY --version)"
success "Python: $($PY --version)"

# ── Clone / update ───────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "به‌روزرسانی کد در $INSTALL_DIR ..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  info "دریافت کد از GitHub..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi
success "کد آماده است."

# ── Virtual environment ───────────────────────────────────────
VENV="$INSTALL_DIR/venv"
info "ساخت محیط مجازی Python..."
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
success "وابستگی‌های Python نصب شد."

# ── Create .env ───────────────────────────────────────────────
ENV="$INSTALL_DIR/.env"
if [[ ! -f "$ENV" ]]; then
  cp "$INSTALL_DIR/.env.example" "$ENV"
fi

# ── Interactive config ────────────────────────────────────────
if [[ -t 0 ]] && grep -q "your_telegram_bot_token_here" "$ENV" 2>/dev/null; then
  echo ""
  echo -e "${YELLOW}══ پیکربندی ربات ══${NC}"
  echo "(برای رد کردن هر مرحله Enter بزنید)"
  echo ""

  ask "  📱 Telegram Bot Token:"; read -r TG_TOKEN
  ask "  🔑 Google Client ID:  "; read -r G_ID
  ask "  🔒 Google Client Secret:"; read -r G_SECRET
  ask "  🌐 OAuth Redirect URI [http://localhost:8080/oauth/callback]:"; read -r REDIR
  REDIR="${REDIR:-http://localhost:8080/oauth/callback}"
  ask "  👤 Admin Telegram ID(s) [comma-separated]:"; read -r ADMINS
  ask "  📢 Required Channels [@chan1,@chan2]:"; read -r CHANNELS

  # Generate encryption key
  ENC_KEY=$("$VENV/bin/python3" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

  [[ -n "$TG_TOKEN"  ]] && sed -i "s|your_telegram_bot_token_here|$TG_TOKEN|g"       "$ENV"
  [[ -n "$G_ID"      ]] && sed -i "s|your_client_id.apps.googleusercontent.com|$G_ID|g" "$ENV"
  [[ -n "$G_SECRET"  ]] && sed -i "s|your_client_secret|$G_SECRET|g"                  "$ENV"
  [[ -n "$ADMINS"    ]] && sed -i "s|^ADMIN_IDS=.*|ADMIN_IDS=$ADMINS|g"               "$ENV"
  [[ -n "$CHANNELS"  ]] && sed -i "s|^REQUIRED_CHANNELS=.*|REQUIRED_CHANNELS=$CHANNELS|g" "$ENV"
  sed -i "s|your_fernet_key_here|$ENC_KEY|g"        "$ENV"
  sed -i "s|http://localhost:8080/oauth/callback|$REDIR|g" "$ENV"

  success "فایل .env پیکربندی شد."
  success "کلید رمزنگاری ایجاد شد: ${ENC_KEY:0:20}..."
fi

# ── System user ───────────────────────────────────────────────
if ! id drivebot &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin drivebot
fi
chown -R drivebot:drivebot "$INSTALL_DIR"
chmod 600 "$ENV"   # env file readable only by owner

# ── systemd service ───────────────────────────────────────────
cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=Telegram Drive Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=drivebot
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV
ExecStart=$VENV/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE"
success "سرویس systemd ثبت شد."

# ── Start ─────────────────────────────────────────────────────
if grep -q "your_telegram_bot_token_here" "$ENV" 2>/dev/null; then
  warn "فایل .env کامل نشده. سرویس شروع نمی‌شود."
  warn "ویرایش کنید: nano $ENV"
  warn "سپس اجرا کنید: sudo systemctl start $SERVICE"
else
  systemctl restart "$SERVICE"
  success "ربات شروع به کار کرد!"
fi

# ── Summary ───────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ نصب با موفقیت انجام شد!                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
printf "  %-22s %s\n" "مسیر نصب:"     "$INSTALL_DIR"
printf "  %-22s %s\n" "فایل تنظیمات:" "$ENV"
echo ""
echo "  دستورات مدیریت:"
echo -e "  ${CYAN}sudo systemctl start   $SERVICE${NC}"
echo -e "  ${CYAN}sudo systemctl stop    $SERVICE${NC}"
echo -e "  ${CYAN}sudo systemctl restart $SERVICE${NC}"
echo -e "  ${CYAN}sudo journalctl -u $SERVICE -f${NC}    ← مشاهده لاگ"
echo ""
echo "  به‌روزرسانی:"
echo -e "  ${CYAN}sudo bash $INSTALL_DIR/install.sh${NC}"
echo ""
