#!/bin/bash
# WhatsApp Dashboard — Lightsail/EC2 Setup Script
# Run once on a fresh Ubuntu 22.04 instance
# Usage: bash setup.sh yourdomain.com

set -e

DOMAIN=${1:-""}
APP_DIR="/home/ubuntu/whatsapp-dashboard"
SERVICE_NAME="whatsapp-dashboard"

echo "===================================================="
echo " WhatsApp Dashboard — Server Setup"
echo "===================================================="

# ── System packages ──────────────────────────────────────
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git

# ── Python venv + dependencies ────────────────────────────
echo "[2/6] Setting up Python environment..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
deactivate

mkdir -p "$APP_DIR/logs"

# ── Gunicorn config ───────────────────────────────────────
echo "[3/6] Writing gunicorn config..."
cat > "$APP_DIR/gunicorn_config.py" << 'GUNICORN'
import os

bind = "127.0.0.1:5000"
workers = 1
worker_class = "gthread"
threads = 4
timeout = 120
graceful_timeout = 30
keepalive = 5
preload_app = True
max_requests = 500
max_requests_jitter = 50

_log_dir = "/home/ubuntu/whatsapp-dashboard/logs"
os.makedirs(_log_dir, exist_ok=True)
accesslog = f"{_log_dir}/access.log"
errorlog  = f"{_log_dir}/error.log"
loglevel  = os.getenv("LOG_LEVEL", "info").lower()
proc_name = "whatsapp-dashboard"
GUNICORN

# ── Systemd service ───────────────────────────────────────
echo "[4/6] Creating systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << SERVICE
[Unit]
Description=WhatsApp Dashboard
After=network.target

[Service]
User=ubuntu
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/venv/bin/gunicorn app:app --config ${APP_DIR}/gunicorn_config.py
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5
StandardOutput=append:${APP_DIR}/logs/app.log
StandardError=append:${APP_DIR}/logs/app.log

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# ── Nginx ─────────────────────────────────────────────────
echo "[5/6] Configuring nginx..."
sudo tee /etc/nginx/sites-available/${SERVICE_NAME} > /dev/null << NGINX
server {
    listen 80;
    server_name ${DOMAIN:-_};

    client_max_body_size 10M;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_set_header   X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/${SERVICE_NAME} /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# ── SSL ───────────────────────────────────────────────────
echo "[6/6] SSL setup..."
if [ -n "$DOMAIN" ]; then
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@${DOMAIN}" --redirect
    echo "SSL certificate installed for $DOMAIN"
else
    echo "No domain provided — skipping SSL (HTTP only)"
    echo "Run later: sudo certbot --nginx -d yourdomain.com"
fi

# ── Start ─────────────────────────────────────────────────
sudo systemctl start "$SERVICE_NAME"

PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_IP")

echo ""
echo "===================================================="
echo " Setup complete!"
echo ""
if [ -n "$DOMAIN" ]; then
echo " App URL:     https://${DOMAIN}"
echo " Webhook URL: https://${DOMAIN}/webhook   ← set this in Meta"
else
echo " App URL:     http://${PUBLIC_IP}"
echo " (Add a domain + run certbot for HTTPS)"
fi
echo ""
echo " Commands:"
echo "   sudo systemctl status  $SERVICE_NAME"
echo "   sudo systemctl restart $SERVICE_NAME"
echo "   tail -f $APP_DIR/logs/app.log"
echo "===================================================="
