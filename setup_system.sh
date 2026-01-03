#!/bin/bash
# Setup script for NPS IVR system services (requires sudo)

set -e

echo "Installing systemd service..."
sudo cp /home/tfox/timfox456/nps_ivr/nps-ivr.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nps-ivr.service
sudo systemctl start nps-ivr.service

echo "Installing nginx configuration (HTTP-only for now)..."
sudo cp /home/tfox/timfox456/nps_ivr/npaai-nginx-http-only.conf /etc/nginx/sites-available/npaai
sudo ln -sf /etc/nginx/sites-available/npaai /etc/nginx/sites-enabled/npaai

echo "Testing nginx configuration..."
sudo nginx -t

echo "Restarting nginx..."
sudo systemctl restart nginx

echo ""
echo "Setup complete!"
echo "- FastAPI service: sudo systemctl status nps-ivr"
echo "- Nginx status: sudo systemctl status nginx"
echo "- View logs: sudo journalctl -u nps-ivr -f"
