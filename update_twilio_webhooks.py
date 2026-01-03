#!/usr/bin/env python3
"""
Script to update Twilio webhooks for ALL configured phone numbers
"""
import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

# Get Twilio credentials
account_sid = os.getenv('TWILIO_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')

# All phone numbers to configure
PHONE_NUMBERS = [
    "+16198530829",  # Primary number
    "+18777145508",  # Toll-free number
]

# Production URLs
BASE_URL = "https://cali-imperialistic-brittney.ngrok-free.dev"
SMS_URL = f"{BASE_URL}/twilio/sms"
# Using proxied handler (reliable, tested production-ready)
VOICE_URL = f"{BASE_URL}/twilio/voice-realtime-proxied"

print("=" * 70)
print("Updating Twilio Webhooks for Multiple Numbers")
print("=" * 70)
print(f"Base URL: {BASE_URL}")
print(f"SMS URL: {SMS_URL}")
print(f"Voice URL: {VOICE_URL}")
print()

# Initialize Twilio client
client = Client(account_sid, auth_token)

success_count = 0
error_count = 0

for phone_number in PHONE_NUMBERS:
    print(f"Processing {phone_number}...")

    try:
        # Find the phone number
        phone_numbers = client.incoming_phone_numbers.list(phone_number=phone_number)

        if not phone_numbers:
            print(f"  ⚠️  Not found in Twilio account (skipping)")
            error_count += 1
            continue

        phone_number_sid = phone_numbers[0].sid

        # Update the webhooks
        updated_number = client.incoming_phone_numbers(phone_number_sid).update(
            sms_url=SMS_URL,
            sms_method='POST',
            voice_url=VOICE_URL,
            voice_method='POST'
        )

        print(f"  ✅ Updated successfully!")
        print(f"     SMS: {updated_number.sms_url}")
        print(f"     Voice: {updated_number.voice_url}")
        success_count += 1

    except Exception as e:
        print(f"  ❌ Error: {e}")
        error_count += 1

    print()

print("=" * 70)
print(f"Summary: {success_count} updated, {error_count} errors")
print("=" * 70)

if success_count > 0:
    print()
    print("🎉 You can now send SMS or call any configured number to test!")
    print()
    print("Configured numbers:")
    for phone_number in PHONE_NUMBERS:
        print(f"  • {phone_number}")

if error_count > 0:
    exit(1)
