#!/bin/bash
# Start ngrok tunnel in the background

# Start ngrok and save output
ngrok http 8000 --log=stdout > /tmp/ngrok.log 2>&1 &

echo "Starting ngrok tunnel..."
sleep 3

# Get the public URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*\.ngrok[^"]*' | head -1)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Error: Could not get ngrok URL"
    echo "Check if ngrok is running:"
    echo "  ps aux | grep ngrok"
    echo ""
    echo "View logs:"
    echo "  tail -f /tmp/ngrok.log"
    exit 1
fi

echo "✅ ngrok tunnel started!"
echo ""
echo "Public URL: $NGROK_URL"
echo ""
echo "View ngrok dashboard: http://localhost:4040"
echo ""
echo "Next step: Update Twilio webhooks"
echo "Run this command with your ngrok URL:"
echo ""
echo "  python update_twilio_webhooks.py"
echo ""
echo "But first edit the script to change BASE_URL to: $NGROK_URL"
echo ""
echo "To stop ngrok: pkill ngrok"
