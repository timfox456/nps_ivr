#!/bin/bash
# Install and setup ngrok on the server

set -e

echo "Installing ngrok..."

# Download ngrok
cd /tmp
wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz

# Extract
tar xzf ngrok-v3-stable-linux-amd64.tgz

# Move to user bin
sudo mv ngrok /usr/local/bin/

# Clean up
rm ngrok-v3-stable-linux-amd64.tgz

echo "✅ ngrok installed successfully!"
echo ""
echo "Next steps:"
echo "1. If you have an ngrok account, authenticate with:"
echo "   ngrok config add-authtoken YOUR_TOKEN"
echo ""
echo "2. Start ngrok tunnel:"
echo "   ngrok http 8000"
echo ""
echo "3. Copy the HTTPS URL from ngrok output"
echo "4. Run: python update_twilio_webhooks.py"
echo "   (Edit the script to use your ngrok URL first)"
