#!/usr/bin/env bash
# V2Ray Monitor Seller installer
# Safe for: curl ... | bash
# Do not use `set -u`: environment variables are optional.
set -Ee

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root" >&2
    exit 1
fi

APP="/opt/v2ray-monitor-seller"
REPO="https://github.com/TheOnlyOneWithAi/v2ray_monitor_seller.git"
TTY="/dev/tty"

prompt() {
    _prompt_value=""
    while [ -z "$_prompt_value" ]; do
        printf '%s: ' "$1" > "$TTY"
        IFS= read -r _prompt_value < "$TTY" || {
            echo "Unable to read interactive input from $TTY" >&2
            exit 1
        }
    done
    printf '%s' "$_prompt_value"
}

prompt_optional() {
    _prompt_value=""
    printf '%s: ' "$1" > "$TTY"
    IFS= read -r _prompt_value < "$TTY" || _prompt_value=""
    printf '%s' "$_prompt_value"
}

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates git python3 python3-venv python3-pip

TOKEN="${BOT_TOKEN:-}"
if [ -z "$TOKEN" ]; then
    TOKEN="$(prompt 'Telegram Bot Token')"
fi

ADMIN_IDS_VALUE="${ADMIN_IDS:-}"
if [ -z "$ADMIN_IDS_VALUE" ]; then
    ADMIN_IDS_VALUE="$(prompt 'Admin Telegram ID(s), comma-separated')"
fi

PORT="${WEB_PORT:-}"
if [ -z "$PORT" ]; then
    PORT="$(prompt_optional 'Web Port [8090]')"
fi
[ -z "$PORT" ] && PORT="8090"

case "$PORT" in
    ''|*[!0-9]*)
        echo "Invalid WEB_PORT: $PORT" >&2
        exit 1
        ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    echo "WEB_PORT must be between 1 and 65535" >&2
    exit 1
fi

mkdir -p /opt
if [ -d "$APP/.git" ]; then
    git -C "$APP" fetch --depth=1 origin main
    git -C "$APP" reset --hard origin/main
else
    rm -rf "$APP"
    git clone --depth=1 --branch main "$REPO" "$APP"
fi

cd "$APP"
python3 -m venv .venv
. "$APP/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
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

cat > /etc/systemd/system/v2ray-monitor-seller.service <<EOF
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
    echo "ERROR: seller service failed to start" >&2
    exit 1
fi

echo ""
echo "V2Ray Monitor Seller installed successfully."
echo "Web Port: $PORT"
echo "Service: systemctl status v2ray-monitor-seller"
