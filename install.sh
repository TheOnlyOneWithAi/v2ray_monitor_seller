#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
APP="/opt/v2ray-monitor-seller"
MONITOR_APP="/opt/v2ray-monitor"
REPO="https://github.com/TheOnlyOneWithAi/v2ray_monitor_seller.git"
TTY=/dev/tty
prompt(){ local v=''; while [ -z "$v" ]; do printf '%s: ' "$1" >"$TTY"; IFS= read -r v <"$TTY" || exit 1; done; printf '%s' "$v"; }
prompt_optional(){ local v=''; printf '%s: ' "$1" >"$TTY"; IFS= read -r v <"$TTY" || v=''; printf '%s' "$v"; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates git python3 python3-venv python3-pip
TOKEN="${SELLER_BOT_TOKEN:-${BOT_TOKEN:-}}"
[ -n "$TOKEN" ] || TOKEN="$(prompt 'Seller Telegram Bot Token (must be DIFFERENT from Monitor token)')"
ADMIN_IDS_VALUE="${ADMIN_IDS:-}"
[ -n "$ADMIN_IDS_VALUE" ] || ADMIN_IDS_VALUE="$(prompt 'Admin Telegram ID(s), comma-separated')"
PORT="${WEB_PORT:-8090}"
case "$PORT" in ''|*[!0-9]*) echo "Invalid WEB_PORT: $PORT" >&2; exit 1;; esac
# Automatically link Seller to the installed Monitor.
MONITOR_API_URL="${MONITOR_API_URL:-}"
MONITOR_API_TOKEN="${MONITOR_API_TOKEN:-}"
if [ -f "$MONITOR_APP/.env" ]; then
    [ -n "$MONITOR_API_TOKEN" ] || MONITOR_API_TOKEN="$(sed -n 's/^SELLER_API_TOKEN=//p' "$MONITOR_APP/.env" | head -n1 | sed 's/^"//; s/"$//')"
    [ -n "$MONITOR_API_URL" ] || MONITOR_API_URL="$(sed -n 's/^WEB_PORT=//p' "$MONITOR_APP/.env" | head -n1 | sed 's/^"//; s/"$//')"
    [ -n "$MONITOR_API_URL" ] && MONITOR_API_URL="http://127.0.0.1:${MONITOR_API_URL}"
fi
MONITOR_API_URL="${MONITOR_API_URL:-http://127.0.0.1:8091}"
MONITOR_API_TOKEN="${MONITOR_API_TOKEN:-}"
[ -n "$MONITOR_API_TOKEN" ] || MONITOR_API_TOKEN="$(prompt 'Monitor SELLER_API_TOKEN (only if Monitor was not installed here)')"
MONITOR_WEBAPP_URL="${MONITOR_WEBAPP_URL:-http://127.0.0.1:8091}"
mkdir -p /opt
if [ -d "$APP/.git" ]; then
    git -C "$APP" config --local --add safe.directory "$APP" 2>/dev/null || true
    git -C "$APP" fetch --depth=1 origin main
    git -C "$APP" reset --hard origin/main
else
    rm -rf "$APP"
    git clone --depth=1 --branch main "$REPO" "$APP"
fi
cd "$APP"
python3 -m venv .venv
. "$APP/.venv/bin/activate"
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt
id v2ray-seller >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin v2ray-seller
KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
mkdir -p data
cat > .env <<EOF
SELLER_BOT_TOKEN=$TOKEN
ADMIN_IDS=$ADMIN_IDS_VALUE
WEB_PORT=$PORT
DATABASE_URL=sqlite+aiosqlite:///$APP/data/seller.db
ENCRYPTION_KEY=$KEY
MONITOR_API_URL=$MONITOR_API_URL
MONITOR_API_TOKEN=$MONITOR_API_TOKEN
MONITOR_WEBAPP_URL=$MONITOR_WEBAPP_URL
EOF
chown -R v2ray-seller:v2ray-seller "$APP"
chmod 750 "$APP"
chown v2ray-seller:v2ray-seller .env
chmod 600 .env
chmod 700 "$APP/data"
cat >/etc/systemd/system/v2ray-monitor-seller.service <<EOF
[Unit]
Description=V2Ray Monitor Seller Bot
After=network-online.target v2ray-monitor.service
Wants=network-online.target
[Service]
Type=simple
User=v2ray-seller
Group=v2ray-seller
WorkingDirectory=$APP
EnvironmentFile=$APP/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP/.venv/bin/python -m app.main
Restart=always
RestartSec=5
StartLimitIntervalSec=60
StartLimitBurst=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP/data
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now v2ray-monitor-seller.service
sleep 2
if ! systemctl is-active --quiet v2ray-monitor-seller.service; then journalctl -u v2ray-monitor-seller.service --no-pager -n 80 || true; echo 'ERROR: seller service failed to start' >&2; exit 1; fi
echo "Seller installed successfully."
echo "Service: systemctl status v2ray-monitor-seller"
