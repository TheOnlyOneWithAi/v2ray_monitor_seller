#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
APP="/opt/v2ray-monitor-seller"
REPO="https://github.com/TheOnlyOneWithAi/v2ray_monitor_seller.git"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates git python3 python3-venv python3-pip
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
mkdir -p data
chown -R v2ray-seller:v2ray-seller "$APP"
chmod 750 "$APP" "$APP/data"
if [ ! -f "$APP/data/config.json" ]; then
  sudo -u v2ray-seller "$APP/.venv/bin/python" -c 'from app.config import settings; settings.setup_interactive()'
fi
cat >/etc/systemd/system/v2ray-monitor-seller.service <<EOF
[Unit]
Description=V2Ray Monitor Seller Bot
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5
[Service]
Type=simple
User=v2ray-seller
Group=v2ray-seller
WorkingDirectory=$APP
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
systemd-analyze verify /etc/systemd/system/v2ray-monitor-seller.service
systemctl daemon-reload
systemctl enable v2ray-monitor-seller.service >/dev/null
systemctl restart v2ray-monitor-seller.service
sleep 3
if ! systemctl is-active --quiet v2ray-monitor-seller.service; then journalctl -u v2ray-monitor-seller.service --no-pager -n 100 || true; exit 1; fi
echo "Seller installed successfully. No .env is used."
