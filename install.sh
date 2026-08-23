#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${EUID:-0} -eq 0 ]] || { echo 'Run as root'; exit 1; }
APP=/opt/v2ray-monitor-seller
REPO=https://github.com/TheOnlyOneWithAi/v2ray_monitor_seller.git
ask(){ local v=''; while [[ -z "$v" ]]; do read -r -p "$1: " v; done; printf '%s' "$v"; }
apt-get update -y && apt-get install -y ca-certificates git python3 python3-venv python3-pip

# Never reference an unset variable under `set -u`.
TOKEN="${BOT_TOKEN-}"
if [[ -z "$TOKEN" ]]; then TOKEN="$(ask 'Telegram Bot Token')"; fi
ADMIN_IDS_VALUE="${ADMIN_IDS-}"
if [[ -z "$ADMIN_IDS_VALUE" ]]; then ADMIN_IDS_VALUE="${ADMINS-}"; fi
if [[ -z "$ADMIN_IDS_VALUE" ]]; then ADMIN_IDS_VALUE="$(ask 'Admin Telegram ID(s), comma-separated')"; fi
PORT="${WEB_PORT-8090}"

mkdir -p /opt
if [[ -d "$APP/.git" ]]; then git -C "$APP" fetch origin main && git -C "$APP" reset --hard origin/main; else rm -rf "$APP" && git clone --depth=1 "$REPO" "$APP"; fi
cd "$APP"
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
KEY="$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
mkdir -p data
cat > .env <<EOF
BOT_TOKEN=$TOKEN
ADMIN_IDS=$ADMIN_IDS_VALUE
WEB_PORT=$PORT
DATABASE_URL=sqlite+aiosqlite:///./data/seller.db
ENCRYPTION_KEY=$KEY
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
systemctl daemon-reload
systemctl enable --now v2ray-monitor-seller.service
if ! systemctl is-active --quiet v2ray-monitor-seller.service; then
  journalctl -u v2ray-monitor-seller.service --no-pager -n 80 || true
  echo 'ERROR: seller service failed to start' >&2
  exit 1
fi
echo "Installed: http://SERVER-IP:$PORT"
