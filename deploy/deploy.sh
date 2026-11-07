#!/bin/bash
# Pull latest code and restart the app
# This script is designed to run on the production server and auto-deploy via GitHub Actions.
# It derives the app directory from its own location, making it portable across server paths.

set -e

# Derive APP_DIR from this script's location (works regardless of where it's called from)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

# Allow override via environment variable for testing/flexibility
APP_DIR="${DEPLOY_APP_DIR:-$APP_DIR}"

# Service name defaults to "whatsapp-dashboard" but can be overridden
SERVICE_NAME="${DEPLOY_SERVICE_NAME:-whatsapp-dashboard}"

echo "Deploying from: $APP_DIR"
echo "Service name: $SERVICE_NAME"

echo "Pulling latest code..."
cd "$APP_DIR"
git pull origin main

echo "Installing any new dependencies..."
source venv/bin/activate
pip install -r requirements.txt -q
deactivate

echo "Restarting service..."
sudo systemctl restart "$SERVICE_NAME"

echo "Waiting for service to stabilize..."
sleep 2

echo "Checking service status..."
if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "ERROR: Service failed to start"
  sudo systemctl status "$SERVICE_NAME" --no-pager -l
  exit 1
fi

echo "Service is active. Checking health..."
if command -v curl &> /dev/null; then
  if curl -s http://localhost:5000 > /dev/null 2>&1; then
    echo "Health check passed (localhost:5000 responding)"
  else
    echo "WARNING: localhost:5000 not responding (may require login or be behind reverse proxy)"
  fi
fi

echo "Deploy successful. Status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l
