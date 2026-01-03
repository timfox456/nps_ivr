# Switching from ngrok to Production Server

## Current Status

✅ **Server Setup Complete:**
- FastAPI app running on port 8000
- Nginx configured and running
- Service auto-starts on reboot
- Domain: npaai.dev.npauctions.com (behind Cloudflare)
- Server IP: 10.60.2.19

## Steps to Switch from ngrok to Production

### Step 1: Set Up SSL Certificate

Since the domain is behind Cloudflare, you have two options:

#### Option A: Use Cloudflare SSL (Recommended - Easiest)

1. Go to Cloudflare dashboard for npauctions.com
2. SSL/TLS settings → Set to "Full" or "Full (strict)" mode
3. Origin Certificates → Create an origin certificate
4. Save the certificate and key to the server

```bash
# Create the certificate files (paste from Cloudflare)
sudo nano /etc/ssl/certs/npaai.dev.npauctions.com.crt
sudo nano /etc/ssl/private/npaai.dev.npauctions.com.key

# Set proper permissions
sudo chmod 644 /etc/ssl/certs/npaai.dev.npauctions.com.crt
sudo chmod 600 /etc/ssl/private/npaai.dev.npauctions.com.key
```

Then update nginx:
```bash
sudo cp /home/tfox/timfox456/nps_ivr/npaai-nginx.conf /etc/nginx/sites-available/npaai
sudo nginx -t
sudo systemctl reload nginx
```

#### Option B: Use Let's Encrypt with Cloudflare DNS

If Cloudflare is in "DNS only" mode (not proxied):
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d npaai.dev.npauctions.com
```

### Step 2: Verify SSL is Working

```bash
# Test locally
curl https://npaai.dev.npauctions.com/health

# Should return: {"ok":true}
```

### Step 3: Update Twilio Webhooks

You need to update the Twilio phone number (+16198530829) webhooks from your ngrok URLs to production.

#### Using Twilio Console (Web Interface):

1. Go to https://console.twilio.com
2. Navigate to: **Phone Numbers → Manage → Active Numbers**
3. Click on **+16198530829**
4. Update these fields:

   **Messaging Configuration:**
   - A MESSAGE COMES IN: **Webhook**
   - URL: `https://npaai.dev.npauctions.com/twilio/sms`
   - HTTP: **POST**

   **Voice Configuration:**
   - A CALL COMES IN: **Webhook**
   - URL: `https://npaai.dev.npauctions.com/twilio/voice`
   - HTTP: **POST**

5. Click **Save**

#### Using Twilio CLI (if installed):

```bash
twilio phone-numbers:update +16198530829 \
  --sms-url="https://npaai.dev.npauctions.com/twilio/sms" \
  --voice-url="https://npaai.dev.npauctions.com/twilio/voice"
```

### Step 4: Test the Webhooks

After updating Twilio:

1. **Test SMS:**
   - Send a text message to +16198530829
   - You should receive the initial greeting

2. **Test Voice:**
   - Call +16198530829
   - You should hear the voice greeting

3. **Monitor Logs:**
   ```bash
   # Watch application logs
   sudo journalctl -u nps-ivr -f

   # Watch nginx logs
   sudo tail -f /var/log/nginx/npaai_access.log
   ```

### Step 5: Stop ngrok (On Your Laptop)

Once you've verified production is working:
- Stop the ngrok process on your laptop
- Stop the local FastAPI server
- The production server will now handle all traffic

## Troubleshooting

### Twilio Can't Reach the Server

**Check Cloudflare Settings:**
- Ensure the A record for npaai.dev.npauctions.com points to 10.60.2.19
- Check SSL/TLS mode is set correctly
- Verify firewall rules allow traffic

**Check Server:**
```bash
# Verify service is running
sudo systemctl status nps-ivr

# Check nginx
sudo systemctl status nginx

# Test locally
curl https://npaai.dev.npauctions.com/health
```

### SSL Certificate Errors

If using Cloudflare origin certificates, ensure:
- Certificate includes the full chain
- Private key is correct and readable by nginx
- Nginx config points to correct paths

### Webhooks Return Errors

Check application logs:
```bash
sudo journalctl -u nps-ivr -n 100
```

Common issues:
- Database permissions
- Environment variables not loaded
- OpenAI API key issues

## Verification Checklist

Before switching:
- [ ] SSL certificate installed and working
- [ ] `curl https://npaai.dev.npauctions.com/health` returns `{"ok":true}`
- [ ] Twilio webhooks updated to production URLs
- [ ] Test SMS to +16198530829 works
- [ ] Test call to +16198530829 works
- [ ] Logs show requests coming through
- [ ] ngrok stopped on laptop

## Current Configuration

**Phone Number:** +16198530829
**Old URLs (ngrok):** https://YOUR-NGROK-ID.ngrok.io/*
**New URLs (production):**
- SMS: `https://npaai.dev.npauctions.com/twilio/sms`
- Voice: `https://npaai.dev.npauctions.com/twilio/voice`

## Important Notes

- **Twilio requires HTTPS** for webhooks (not HTTP)
- The app is already running and will handle requests automatically
- Cloudflare provides DDoS protection and caching
- All conversation data is stored in `/home/tfox/timfox456/nps_ivr/nps_ivr.db`
- The service auto-restarts on failure and server reboot

## Next Steps After Switching

1. Monitor the first few calls/texts to ensure everything works
2. Check database to verify leads are being created
3. Consider setting up monitoring/alerting
4. Update any documentation that references ngrok URLs
