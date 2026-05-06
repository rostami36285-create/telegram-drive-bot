#!/usr/bin/env bash
# ============================================================
#  Telegram Drive Bot — One-line installer for Linux servers
#  Usage:
#    curl -fsSL https://raw.githubusercontent.com/GITHUB_USER/telegram-drive-bot/main/install.sh | bash
#  Or clone the repo and run:
#    bash install.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

INSTALL_DIR="${INSTALL_DIR:-/opt/telegram-drive-bot}"
SERVICE_NAME="telegram-drive-bot"
REPO_URL="https://github.com/rostami36285-create/telegram-drive-bot.git"
PYTHON_MIN="3.10"

# ── Root check ──────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  die "این اسکریپت نیاز به دسترسی root دارد. با sudo اجرا کنید."
fi

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Telegram Drive Bot — Installer         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Detect OS ───────────────────────────────────────────────
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  OS_ID="$ID"
else
  die "سیستم‌عامل شناخته‌شده نیست."
fi

info "سیستم‌عامل: $PRETTY_NAME"

# ── Install system dependencies ─────────────────────────────
info "نصب پیش‌نیازهای سیستم..."
case "$OS_ID" in
  ubuntu|debian)
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv git curl 2>/dev/null
    ;;
  centos|rhel|fedora|rocky|almalinux)
    if command -v dnf &>/dev/null; then
      dnf install -y python3 python3-pip git curl 2>/dev/null
    else
      yum install -y python3 python3-pip git curl 2>/dev/null
    fi
    ;;
  arch)
    pacman -Sy --noconfirm python python-pip git curl 2>/dev/null
    ;;
  *)
    warn "توزیع ناشناخته ($OS_ID). نصب پیش‌نیازها را به‌صورت دستی انجام دهید."
    ;;
esac
success "پیش‌نیازهای سیستم نصب شد."

# ── Check Python version ─────────────────────────────────────
PYTHON_BIN=$(command -v python3 || command -v python || die "Python یافت نشد.")
PY_VER=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
  success "Python $PY_VER یافت شد."
else
  die "Python $PYTHON_MIN یا بالاتر مورد نیاز است. نسخه فعلی: $PY_VER"
fi

# ── Clone or update repo ─────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "به‌روزرسانی نسخه موجود در $INSTALL_DIR ..."
  git -C "$INSTALL_DIR" pull --ff-only
  success "کد به‌روز شد."
else
  info "دریافت کد از GitHub..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  success "کد در $INSTALL_DIR کلون شد."
fi

# ── Virtual environment ──────────────────────────────────────
VENV="$INSTALL_DIR/venv"
info "ساخت محیط مجازی Python..."
"$PYTHON_BIN" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
success "وابستگی‌های Python نصب شد."

# ── Create .env if not exists ────────────────────────────────
ENV_FILE="$INSTALL_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$INSTALL_DIR/.env.example" "$ENV_FILE"
  warn "فایل .env ساخته شد. حتماً آن را ویرایش کنید:"
  warn "  nano $ENV_FILE"
fi

# ── Collect config interactively (if running from terminal) ──
if [[ -t 0 && ! -s "$ENV_FILE" || $(grep -c "your_telegram_bot_token_here" "$ENV_FILE") -gt 0 ]]; then
  echo ""
  echo -e "${YELLOW}══ پیکربندی ربات ══${NC}"
  echo "اطلاعات زیر را وارد کنید (Enter برای رد کردن):"
  echo ""

  read -rp "  Telegram Bot Token: " TG_TOKEN
  read -rp "  Google Client ID:   " G_CLIENT_ID
  read -rp "  Google Client Secret: " G_CLIENT_SECRET
  read -rp "  OAuth Redirect URI [http://localhost:8080/oauth/callback]: " REDIRECT_URI
  REDIRECT_URI="${REDIRECT_URI:-http://localhost:8080/oauth/callback}"

  if [[ -n "$TG_TOKEN" ]]; then
    sed -i "s|your_telegram_bot_token_here|$TG_TOKEN|g" "$ENV_FILE"
  fi
  if [[ -n "$G_CLIENT_ID" ]]; then
    sed -i "s|your_google_client_id.apps.googleusercontent.com|$G_CLIENT_ID|g" "$ENV_FILE"
  fi
  if [[ -n "$G_CLIENT_SECRET" ]]; then
    sed -i "s|your_google_client_secret|$G_CLIENT_SECRET|g" "$ENV_FILE"
  fi
  sed -i "s|http://localhost:8080/oauth/callback|$REDIRECT_URI|g" "$ENV_FILE"

  success "فایل .env پیکربندی شد."
fi

# ── Create dedicated system user ─────────────────────────────
if ! id "drivebot" &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin drivebot
  success "کاربر سیستمی 'drivebot' ساخته شد."
fi
chown -R drivebot:drivebot "$INSTALL_DIR"

# ── systemd service ──────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Telegram Drive Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=drivebot
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
success "سرویس systemd ثبت شد."

# ── Start service ────────────────────────────────────────────
if grep -q "your_telegram_bot_token_here" "$ENV_FILE" 2>/dev/null; then
  warn "فایل .env هنوز پیکربندی نشده. سرویس شروع نشد."
  warn "پس از ویرایش .env اجرا کنید:"
  warn "  sudo systemctl start $SERVICE_NAME"
else
  systemctl restart "$SERVICE_NAME"
  success "ربات شروع به کار کرد."
fi

# ── Summary ──────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   نصب با موفقیت انجام شد!               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  مسیر نصب    : $INSTALL_DIR"
echo "  فایل تنظیمات: $ENV_FILE"
echo ""
echo "  دستورات مدیریت:"
echo -e "  ${CYAN}sudo systemctl start   $SERVICE_NAME${NC}"
echo -e "  ${CYAN}sudo systemctl stop    $SERVICE_NAME${NC}"
echo -e "  ${CYAN}sudo systemctl restart $SERVICE_NAME${NC}"
echo -e "  ${CYAN}sudo journalctl -u $SERVICE_NAME -f${NC}   (مشاهده لاگ)"
echo ""
echo "  برای به‌روزرسانی:"
echo -e "  ${CYAN}sudo bash $INSTALL_DIR/install.sh${NC}"
echo ""
