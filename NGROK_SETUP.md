# Using ngrok on the Server (Simple Solution!)

This is the easiest way to get HTTPS without dealing with certificates or Cloudflare.

## Why ngrok?

- ✅ Provides HTTPS automatically (Twilio requirement)
- ✅ No SSL certificate configuration needed
- ✅ Works exactly like it did on your laptop
- ✅ Perfect for dev/test servers
- ✅ Free tier available

## Quick Setup

### Step 1: Install ngrok

```bash
./setup_ngrok.sh
```

### Step 2: (Optional) Authenticate ngrok

If you have an ngrok account (recommended for longer sessions):

```bash
ngrok config add-authtoken YOUR_AUTHTOKEN
```

Get your token from: https://dashboard.ngrok.com/get-started/your-authtoken

### Step 3: Start ngrok Tunnel

```bash
./start_ngrok.sh
```

This will:
- Start ngrok in the background
- Show you the public HTTPS URL
- Keep running even if you disconnect from SSH

### Step 4: Update Twilio Webhooks

Edit the update script with your ngrok URL:

```bash
nano update_twilio_webhooks.py
```

Change this line:
```python
BASE_URL = "https://npaai.dev.npauctions.com"
```

To your ngrok URL:
```python
BASE_URL = "https://abc123.ngrok.io"  # Use YOUR ngrok URL
```

Then run:
```bash
source .venv/bin/activate
python update_twilio_webhooks.py
```

### Step 5: Test It!

Send a text or call +16198530829

Watch the logs:
```bash
sudo journalctl -u nps-ivr -f
```

## Running ngrok Persistently in tmux

Since you're using tmux, you can keep ngrok running in a separate pane:

```bash
# Create new tmux window
Ctrl+B, C

# Start ngrok
ngrok http 8000

# Switch back to your main window
Ctrl+B, P

# Or view ngrok dashboard in browser
curl http://localhost:4040
```

## Managing ngrok

```bash
# Check if ngrok is running
ps aux | grep ngrok

# View ngrok requests (in browser)
# Open: http://localhost:4040

# Stop ngrok
pkill ngrok

# Restart ngrok
ngrok http 8000
```

## Important Notes

### Free vs Paid ngrok

**Free tier:**
- Random URL each time (e.g., https://abc123.ngrok.io)
- URL changes when you restart ngrok
- Limited connections per minute
- Need to update Twilio webhooks each time URL changes

**Paid tier ($8/month):**
- Static subdomain (e.g., https://npa-ivr.ngrok.io)
- URL stays the same
- More connections
- Set Twilio webhooks once

### Keeping ngrok Running

If you want ngrok to survive server reboots, create a systemd service:

```bash
sudo nano /etc/systemd/system/ngrok.service
```

```ini
[Unit]
Description=ngrok tunnel
After=network.target

[Service]
Type=simple
User=tfox
WorkingDirectory=/home/tfox
ExecStart=/usr/local/bin/ngrok http 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ngrok
sudo systemctl start ngrok
```

But note: Free tier URL will still change on restart.

## Comparison: ngrok vs Cloudflare

| Feature | ngrok (Free) | Cloudflare + SSL |
|---------|--------------|------------------|
| Setup time | 2 minutes | 15-30 minutes |
| HTTPS | ✅ Automatic | ⚙️ Requires config |
| Static URL | ❌ Changes on restart | ✅ Static domain |
| Cost | Free | Free |
| Best for | Dev/Test | Production |

## Troubleshooting

### ngrok: command not found
```bash
which ngrok
# If not found, run ./setup_ngrok.sh
```

### Can't access localhost:4040
```bash
# Make sure ngrok is running
ps aux | grep ngrok

# Check ngrok logs
tail -f /tmp/ngrok.log
```

### Twilio webhooks not working
1. Check ngrok URL is correct in Twilio
2. Verify app is running: `curl http://localhost:8000/health`
3. Check ngrok dashboard: http://localhost:4040
4. View app logs: `sudo journalctl -u nps-ivr -f`

---

**Bottom line:** ngrok is the fastest way to get your app working with Twilio on this dev server. Install it, start it, update Twilio, and you're done!
