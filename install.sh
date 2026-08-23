#!/usr/bin/env bash
# V2Ray Monitor Seller installer - safe for curl | bash
set -Ee
[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
APP="/opt/v2ray-monitor-seller"; REPO="https://github.com/TheOnlyOneWithAi/v2ray_monitor_seller.git"; TTY=/dev/tty
prompt(){ local v=''; while [ -z "$v" ]; do printf '%s: ' "$1" >"$TTY"; IFS= read -r v <"$TTY" || exit 1; done; printf '%s' "$v"; }
prompt_optional(){ local v=''; printf '%s: ' "$1" >"$TTY"; IFS= read -r v <"$TTY" || v=''; printf '%s' "$v"; }
export DEBIAN_FRONTEND=noninteractive
apt-get update -y; apt-get install -y ca-certificates git python3 python3-venv python3-pip
TOKEN="${BOT_TOKEN:-}"; [ -n "$TOKEN" ] || TOKEN="$(prompt 'Telegram Bot Token')"
ADMIN_IDS_VALUE="${ADMIN_IDS:-}"; [ -n "$ADMIN_IDS_VALUE" ] || ADMIN_IDS_VALUE="$(prompt 'Admin Telegram ID(s), comma-separated')"
PORT="${WEB_PORT:-}"; [ -n "$PORT" ] || PORT="$(prompt_optional 'Web Port [8090]')"; [ -n "$PORT" ] || PORT=8090
case "$PORT" in ''|*[!0-9]*) echo "Invalid WEB_PORT: $PORT" >&2; exit 1;; esac
MONITOR_API_URL="${MONITOR_API_URL:-}"; [ -n "$MONITOR_API_URL" ] || MONITOR_API_URL="$(prompt_optional 'V2Ray Monitor API URL (e.g. http://127.0.0.1:8000)')"
MONITOR_API_TOKEN="${MONITOR_API_TOKEN:-}"; [ -n "$MONITOR_API_TOKEN" ] || MONITOR_API_TOKEN="$(prompt_optional 'V2Ray Monitor Seller API token')"
MONITOR_WEBAPP_URL="${MONITOR_WEBAPP_URL:-}"; [ -n "$MONITOR_WEBAPP_URL" ] || MONITOR_WEBAPP_URL="$(prompt_optional 'V2Ray Monitor WebApp URL (e.g. https://monitor.example.com)')"
mkdir -p /opt
if [ -d "$APP/.git" ]; then git -C "$APP" fetch --depth=1 origin main; git -C "$APP" reset --hard origin/main; else rm -rf "$APP"; git clone --depth=1 --branch main "$REPO" "$APP"; fi
cd "$APP"; python3 -m venv .venv; . "$APP/.venv/bin/activate"; python -m pip install --upgrade pip; python -m pip install -r requirements.txt
KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"; mkdir -p data
cat > .env <<EOF
BOT_TOKEN=$TOKEN
ADMIN_IDS=$ADMIN_IDS_VALUE
WEB_PORT=$PORT
DATABASE_URL=sqlite+aiosqlite:///./data/seller.db
ENCRYPTION_KEY=$KEY
MONITOR_API_URL=$MONITOR_API_URL
MONITOR_API_TOKEN=$MONITOR_API_TOKEN
MONITOR_WEBAPP_URL=$MONITOR_WEBAPP_URL
EOF
chmod 600 .env
id v2ray-seller >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin v2ray-seller
chown -R v2ray-seller:v2ray-seller "$APP/data"
cat >/etc/systemd/system/v2ray-monitor-seller.service <<EOF
[Unit]
Description=V2Ray Monitor Seller Bot
After=network-online.target
Wants=network-online.target
[Service]
User=v2ray-seller
Group=v2ray-seller
WorkingDirectory=$APP
EnvironmentFile=$APP/.env
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
systemctl daemon-reload; systemctl enable --now v2ray-monitor-seller.service
if ! systemctl is-active --quiet v2ray-monitor-seller.service; then journalctl -u v2ray-monitor-seller.service --no-pager -n 80 || true; echo 'ERROR: seller service failed to start' >&2; exit 1; fi
echo "Seller installed successfully. WebApp: $MONITOR_WEBAPP_URL"; echo "Service: systemctl status v2ray-monitor-seller"
