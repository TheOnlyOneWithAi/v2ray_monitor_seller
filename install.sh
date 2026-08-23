#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
APP="/opt/v2ray-monitor-seller"
MONITOR_APP="/opt/v2ray-monitor"
REPO="https://github.com/TheOnlyOneWithAi/v2ray_monitor_seller.git"
TTY=/dev/tty
prompt(){ local v=''; while [ -z "$v" ]; do printf '%s: ' "$1" >"$TTY"; IFS= read -r v <"$TTY" || exit 1; done; printf '%s' "$v"; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates git python3 python3-venv python3-pip
TOKEN="${SELLER_BOT_TOKEN:-${BOT_TOKEN:-}}"
[ -n "$TOKEN" ] || TOKEN="$(prompt 'Seller Telegram Bot Token (must be DIFFERENT from Monitor token)')"
ADMIN_IDS_VALUE="${ADMIN_IDS:-}"
[ -n "$ADMIN_IDS_VALUE" ] || ADMIN_IDS_VALUE="$(prompt 'Admin Telegram ID(s), comma-separated')"
PORT="${WEB_PORT:-8090}"
case "$PORT" in ''|*[!0-9]*) echo "Invalid WEB_PORT: $PORT" >&2; exit 1;; esac
(( PORT >= 1 && PORT <= 65535 )) || { echo "Invalid WEB_PORT: $PORT" >&2; exit 1; }
# Seller talks to the Monitor locally. No Seller API token is used.
MONITOR_API_URL="${MONITOR_API_URL:-}"
MONITOR_PORT=""
if [ -f "$MONITOR_APP/.env" ]; then
    MONITOR_PORT="$(sed -n 's/^WEB_PORT=//p' "$MONITOR_APP/.env" | head -n1 | sed 's/^"//; s/"$//')"
    if [ -z "$MONITOR_API_URL" ] && [ -n "$MONITOR_PORT" ]; then MONITOR_API_URL="http://127.0.0.1:${MONITOR_PORT}"; fi
fi
MONITOR_API_URL="${MONITOR_API_URL:-http://127.0.0.1:8091}"
MONITOR_WEBAPP_URL="${MONITOR_WEBAPP_URL:-$MONITOR_API_URL}"
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
SELLER_BOT_TOKEN="$(printf '%s' "$TOKEN" | sed 's/\\/\\\\/g; s/"/\\"/g')"
ADMIN_IDS="$(printf '%s' "$ADMIN_IDS_VALUE" | sed 's/\\/\\\\/g; s/"/\\"/g')"
WEB_PORT="$PORT"
DATABASE_URL="sqlite+aiosqlite:///$APP/data/seller.db"
ENCRYPTION_KEY="$KEY"
MONITOR_API_URL="$(printf '%s' "$MONITOR_API_URL" | sed 's/\\/\\\\/g; s/"/\\"/g')"
MONITOR_WEBAPP_URL="$(printf '%s' "$MONITOR_WEBAPP_URL" | sed 's/\\/\\\\/g; s/"/\\"/g')"
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
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=v2ray-seller
Group=v2ray-seller
WorkingDirectory=$APP
Environment=PYTHONUNBUFFERED=1
ExecStart=$APP/.venv/bin/python -m app.main
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP/data

[Install]
WantedBy=multi-user.target
EOF
systemd-analyze verify /etc/systemd/system/v2ray-monitor-seller.service || { echo 'ERROR: invalid seller systemd unit' >&2; exit 1; }
systemctl daemon-reload
systemctl enable v2ray-monitor-seller.service >/dev/null
systemctl reset-failed v2ray-monitor-seller.service 2>/dev/null || true
systemctl restart v2ray-monitor-seller.service
sleep 2
if ! systemctl is-active --quiet v2ray-monitor-seller.service; then journalctl -u v2ray-monitor-seller.service --no-pager -n 80 || true; echo 'ERROR: seller service failed to start' >&2; exit 1; fi
echo "Seller installed successfully."
echo "Seller API token: NOT REQUIRED"
echo "Service: systemctl status v2ray-monitor-seller"
