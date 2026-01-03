# SSL Certificate Setup Guide

## Option 1: Let's Encrypt (Recommended for production)

### Install Certbot
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

### Get SSL Certificate
```bash
sudo certbot --nginx -d npaai.dev.npauctions.com
```

This will:
- Automatically obtain and install SSL certificate
- Configure nginx with proper SSL settings
- Set up auto-renewal

### Test Auto-Renewal
```bash
sudo certbot renew --dry-run
```

## Option 2: Use Existing SSL Certificates

If you already have SSL certificates, place them in:
- Certificate: `/etc/ssl/certs/npaai.dev.npauctions.com.crt`
- Private Key: `/etc/ssl/private/npaai.dev.npauctions.com.key`

Then use the `npaai-nginx.conf` configuration.

## Option 3: Start with HTTP Only (Testing)

For initial testing without SSL:

1. Use the HTTP-only nginx config:
```bash
sudo cp npaai-nginx-http-only.conf /etc/nginx/sites-available/npaai
sudo ln -sf /etc/nginx/sites-available/npaai /etc/nginx/sites-enabled/npaai
sudo nginx -t
sudo systemctl restart nginx
```

2. Later, upgrade to HTTPS using certbot or by switching to `npaai-nginx.conf`

## Current Status

The application is ready to deploy. You need to:

1. **Choose SSL option** (see above)
2. **Run the setup script** with your password:
   ```bash
   ./setup_system.sh
   ```

   This will:
   - Install and start the systemd service
   - Configure nginx
   - Enable automatic restart on failure

3. **Test the deployment**:
   ```bash
   # Check service status
   sudo systemctl status nps-ivr

   # View logs
   sudo journalctl -u nps-ivr -f

   # Test HTTP endpoint
   curl http://localhost:8000/health
   curl http://npaai.dev.npauctions.com/health
   ```

## Twilio Webhook Configuration

Once the server is running, update Twilio webhooks to:
- SMS: `https://npaai.dev.npauctions.com/twilio/sms`
- Voice: `https://npaai.dev.npauctions.com/twilio/voice`

Use the Twilio Console or CLI:
```bash
twilio phone-numbers:update +16198530829 \
  --sms-url="https://npaai.dev.npauctions.com/twilio/sms" \
  --voice-url="https://npaai.dev.npauctions.com/twilio/voice"
```
