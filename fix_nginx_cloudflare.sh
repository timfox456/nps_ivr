#!/bin/bash
# Fix nginx to work with Cloudflare HTTPS

set -e

echo "Disabling default nginx site..."
sudo rm -f /etc/nginx/sites-enabled/default

echo "Making npaai site also respond to requests without server_name match..."
# This makes our site the default since no other sites are enabled

echo "Testing nginx configuration..."
sudo nginx -t

echo "Reloading nginx..."
sudo systemctl reload nginx

echo ""
echo "Testing endpoints..."
curl -s https://npaai.dev.npauctions.com/health
echo ""
echo ""
echo "✅ Done! Nginx is now configured to work with Cloudflare HTTPS"
echo ""
echo "Next step: Update Twilio webhooks to:"
echo "  SMS: https://npaai.dev.npauctions.com/twilio/sms"
echo "  Voice: https://npaai.dev.npauctions.com/twilio/voice"
