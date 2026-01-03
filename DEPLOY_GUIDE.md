# NPS IVR - Server Deployment Guide

## ✅ What's Already Done

1. ✓ Python 3.11.13 virtual environment created
2. ✓ All dependencies installed
3. ✓ SQLite database initialized
4. ✓ Application tested and working
5. ✓ Systemd service file created
6. ✓ Nginx configuration files created

## 🚀 Next Steps (Run These Commands)

### Step 1: Deploy System Services

Run the setup script with your password:

```bash
./setup_system.sh
```

**Note:** This uses the HTTP-only nginx config for initial testing.

### Step 2: Verify Services Are Running

```bash
# Check FastAPI service
sudo systemctl status nps-ivr

# Check nginx
sudo systemctl status nginx

# View application logs
sudo journalctl -u nps-ivr -f
```

### Step 3: Test the Application

```bash
# Test health endpoint locally
curl http://localhost:8000/health

# Test through nginx (if DNS is configured)
curl http://npaai.dev.npauctions.com/health
```

Expected response: `{"status":"ok"}`

### Step 4: Set Up SSL (Production)

Follow the guide in `SSL_SETUP.md`:

```bash
# Install certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d npaai.dev.npauctions.com
```

### Step 5: Update Twilio Webhooks

Once SSL is configured, update Twilio webhooks:

**Using Twilio Console:**
1. Go to https://console.twilio.com
2. Navigate to Phone Numbers → Manage → Active Numbers
3. Click on +16198530829
4. Set webhooks:
   - SMS: `https://npaai.dev.npauctions.com/twilio/sms` (POST)
   - Voice: `https://npaai.dev.npauctions.com/twilio/voice` (POST)
5. Save

**Using Twilio CLI:**
```bash
twilio phone-numbers:update +16198530829 \
  --sms-url="https://npaai.dev.npauctions.com/twilio/sms" \
  --voice-url="https://npaai.dev.npauctions.com/twilio/voice"
```

## 📁 Configuration Files Created

- `nps-ivr.service` - Systemd service for FastAPI app
- `npaai-nginx.conf` - Nginx config with SSL (for production)
- `npaai-nginx-http-only.conf` - Nginx config without SSL (for testing)
- `setup_system.sh` - Automated setup script
- `SSL_SETUP.md` - SSL certificate setup guide

## 🔧 Useful Commands

### Service Management
```bash
# Start service
sudo systemctl start nps-ivr

# Stop service
sudo systemctl stop nps-ivr

# Restart service
sudo systemctl restart nps-ivr

# View logs
sudo journalctl -u nps-ivr -f

# Check service status
sudo systemctl status nps-ivr
```

### Application Management
```bash
# Test manually (for debugging)
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Check database
sqlite3 nps_ivr.db "SELECT * FROM conversation_sessions ORDER BY created_at DESC LIMIT 5;"
```

### Nginx Management
```bash
# Test nginx config
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx

# View nginx logs
sudo tail -f /var/log/nginx/npaai_access.log
sudo tail -f /var/log/nginx/npaai_error.log
```

## 🛠 Troubleshooting

### Service Won't Start
```bash
# Check logs for errors
sudo journalctl -u nps-ivr -n 50

# Verify environment
source .venv/bin/activate
python -c "from app.main import app; print('Import successful')"
```

### Nginx Issues
```bash
# Test configuration
sudo nginx -t

# Check which sites are enabled
ls -la /etc/nginx/sites-enabled/

# View error logs
sudo tail -f /var/log/nginx/error.log
```

### Port Already in Use
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Or
sudo netstat -tlnp | grep 8000
```

## 🌐 Architecture

```
Internet
    ↓
Nginx (Port 80/443) → npaai.dev.npauctions.com
    ↓
FastAPI (Port 8000) → localhost:8000
    ↓
SQLite Database → /home/tfox/timfox456/nps_ivr/nps_ivr.db
```

## 📊 Monitoring

### Check Application Health
```bash
curl http://localhost:8000/health
```

### View Active Sessions
```bash
sqlite3 nps_ivr.db "SELECT channel, status, COUNT(*) FROM conversation_sessions GROUP BY channel, status;"
```

### Monitor Logs in Real-Time
```bash
# Application logs
sudo journalctl -u nps-ivr -f

# Nginx access logs
sudo tail -f /var/log/nginx/npaai_access.log

# Nginx error logs
sudo tail -f /var/log/nginx/npaai_error.log
```

## 🔐 Security Notes

- Database file permissions: Only readable by tfox user
- Service runs as non-root user (tfox)
- Nginx handles SSL termination
- Twilio webhook signature verification can be enabled in app/main.py

## 📝 Environment Variables

Current configuration in `.env`:
- ✓ TWILIO_SID
- ✓ TWILIO_AUTH_TOKEN
- ✓ TWILIO_PHONE_NUMBER (+16198530829)
- ✓ OPENAI_API_KEY
- ✓ NPA_API_USERNAME
- ✓ NPA_API_PASSWORD

## 🎯 Next Steps After Deployment

1. Test SMS flow by sending a text to +16198530829
2. Test voice flow by calling +16198530829
3. Monitor logs during initial test calls
4. Verify leads are created correctly
5. Set up monitoring/alerting (optional)

---

**Server:** 10.60.2.19
**Domain:** npaai.dev.npauctions.com
**App Port:** 8000
**User:** tfox
**Working Dir:** /home/tfox/timfox456/nps_ivr
