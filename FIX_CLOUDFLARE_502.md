# Fix Cloudflare 502 Error

## Problem
The app works locally (HTTP), but Cloudflare returns 502 errors on HTTPS because it's trying to connect to the origin via HTTPS, but nginx only listens on HTTP.

## Solution: Configure Cloudflare SSL Mode

Go to Cloudflare Dashboard and change SSL/TLS mode to **Flexible**:

### Steps:

1. **Go to Cloudflare Dashboard**
   - Login at https://dash.cloudflare.com
   - Select the `npauctions.com` domain

2. **Navigate to SSL/TLS Settings**
   - Click on **SSL/TLS** in the left sidebar
   - Click on **Overview** tab

3. **Change SSL/TLS Encryption Mode**
   - Select **Flexible** mode
   - This tells Cloudflare: "Use HTTPS to visitors, but HTTP to origin server"

4. **Wait 1-2 minutes** for changes to propagate

5. **Test the connection:**
   ```bash
   curl https://npaai.dev.npauctions.com/health
   ```

   Should return: `{"ok":true}`

## What Each SSL Mode Means:

- **Off**: No HTTPS at all ❌
- **Flexible**: HTTPS (visitor ↔ Cloudflare), HTTP (Cloudflare ↔ origin) ✅ **Use this**
- **Full**: HTTPS both ways, but doesn't validate certificate
- **Full (strict)**: HTTPS both ways, validates certificate (requires SSL on origin)

## After Fixing Cloudflare

Once you see `{"ok":true}` from the curl command, run:

```bash
source .venv/bin/activate
python update_twilio_webhooks.py
```

This will automatically update your Twilio webhooks to the production URLs!

## Verification

After updating Twilio:
1. Send a text to +16198530829
2. Or call +16198530829
3. Watch logs: `sudo journalctl -u nps-ivr -f`

---

## Alternative: Add Self-Signed Certificate (More Complex)

If you can't change Cloudflare settings, you can add a self-signed certificate:

```bash
# Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/npaai.key \
  -out /etc/ssl/certs/npaai.crt \
  -subj "/CN=npaai.dev.npauctions.com"

# Update nginx to listen on 443
sudo nano /etc/nginx/sites-available/npaai
# Add:
#   listen 443 ssl;
#   ssl_certificate /etc/ssl/certs/npaai.crt;
#   ssl_certificate_key /etc/ssl/private/npaai.key;

sudo nginx -t
sudo systemctl reload nginx
```

Then set Cloudflare to **Full** mode (not Full strict).
