#!/bin/bash
# Pull latest code and restart the app
# Run this on the EC2 instance whenever you push updates

set -e

APP_DIR="/home/ubuntu/whatsapp-dashboard"
SERVICE_NAME="whatsapp-dashboard"

echo "Pulling latest code..."
cd "$APP_DIR"
git pull origin main

echo "Installing any new dependencies..."
source venv/bin/activate
pip install -r requirements.txt -q
deactivate

echo "Restarting service..."
sudo systemctl restart "$SERVICE_NAME"

echo "Done. Status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l
