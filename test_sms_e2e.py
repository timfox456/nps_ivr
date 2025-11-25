#!/usr/bin/env python3
"""
End-to-end SMS testing via actual Twilio API.

This script:
1. Sends an SMS to your Twilio number using Twilio's API
2. Waits for Twilio to call your webhook (requires server running)
3. Receives the response via SMS
4. Continues the conversation

Requirements:
- Server must be running (uvicorn app.main:app --reload)
- Webhook must be accessible (via ngrok or deployed)
- Twilio webhook must be configured to point to your server
"""
import argparse
import time
from twilio.rest import Client
from app.config import settings


def send_sms(twilio_client, from_number, to_number, message):
    """Send an SMS and return the message SID"""
    try:
        msg = twilio_client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        print(f"✓ SMS sent: {message[:50]}..." if len(message) > 50 else f"✓ SMS sent: {message}")
        print(f"  Message SID: {msg.sid}")
        return msg.sid
    except Exception as e:
        print(f"✗ Error sending SMS: {e}")
        return None


def wait_for_response(twilio_client, to_number, timeout=30):
    """
    Wait for an SMS response from the Twilio number.

    Note: This checks for new messages TO the user's phone number.
    """
    print(f"  Waiting for response (timeout: {timeout}s)...")
    start_time = time.time()

    # Get initial messages to establish baseline
    initial_messages = twilio_client.messages.list(
        to=to_number,
        limit=1
    )
    initial_sid = initial_messages[0].sid if initial_messages else None

    while time.time() - start_time < timeout:
        # Check for new messages
        messages = twilio_client.messages.list(
            to=to_number,
            limit=1
        )

        if messages and messages[0].sid != initial_sid:
            # New message received
            msg = messages[0]
            print(f"✓ Response received: {msg.body}")
            return msg.body

        time.sleep(2)  # Check every 2 seconds

    print(f"✗ Timeout: No response received within {timeout}s")
    print("  Make sure:")
    print("    1. Your server is running (uvicorn app.main:app --reload)")
    print("    2. Your webhook is accessible (ngrok or deployed)")
    print("    3. Twilio webhook is configured correctly")
    return None


def test_conversation(twilio_client, user_phone, twilio_phone, messages, description):
    """Test a complete conversation"""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print('='*60)

    for i, user_message in enumerate(messages):
        print(f"\n[{i+1}/{len(messages)}] You → Twilio: {user_message}")

        # Send SMS
        msg_sid = send_sms(twilio_client, user_phone, twilio_phone, user_message)
        if not msg_sid:
            print("✗ Failed to send message, aborting test")
            return False

        # Wait for response
        response = wait_for_response(twilio_client, user_phone, timeout=30)
        if response:
            print(f"[{i+1}/{len(messages)}] Twilio → You: {response}")
        else:
            print("✗ No response received, continuing anyway...")

        # Small delay between messages
        time.sleep(2)

    print(f"\n✓ Test completed: {description}")
    return True


def main():
    parser = argparse.ArgumentParser(description='End-to-end SMS testing via Twilio')
    parser.add_argument('--user-phone', required=True, help='Your phone number (must be able to receive SMS)')
    parser.add_argument('--test', choices=['accepted', 'rejected-atv', 'rejected-electric', 'rejected-slingshot'],
                       default='accepted', help='Which test case to run')
    args = parser.parse_args()

    # Validate configuration
    if not all([settings.twilio_sid, settings.twilio_auth_token, settings.twilio_phone_number]):
        print("✗ Error: Twilio credentials not configured in .env")
        return

    print("End-to-End SMS Testing via Twilio API")
    print("="*60)
    print(f"Your phone: {args.user_phone}")
    print(f"Twilio phone: {settings.twilio_phone_number}")
    print(f"Test case: {args.test}")
    print()
    print("⚠ IMPORTANT: Your server must be running and webhook configured!")
    print()

    # Create Twilio client
    client = Client(settings.twilio_sid, settings.twilio_auth_token)

    # Select test case
    test_cases = {
        'accepted': (
            ["Hi", "John Smith", "90210", "john@test.com", "2020 Yamaha Grizzly"],
            "Accepted lead (2020 Yamaha Grizzly)"
        ),
        'rejected-atv': (
            ["Hello", "Jane Doe", "30093", "jane@test.com", "2015 Honda Rancher"],
            "Rejected lead (2015 Honda Rancher - ATV too old)"
        ),
        'rejected-electric': (
            ["Hey", "Mike Wilson", "12345", "mike@test.com", "2023 Zero SR/F"],
            "Rejected lead (2023 Zero SR/F - Electric)"
        ),
        'rejected-slingshot': (
            ["Hi there", "Tom Brown", "60601", "tom@test.com", "2020 Polaris Slingshot"],
            "Rejected lead (2020 Polaris Slingshot)"
        ),
    }

    messages, description = test_cases[args.test]

    input("Press Enter to start the test (make sure server is running)...")

    success = test_conversation(
        client,
        args.user_phone,
        settings.twilio_phone_number,
        messages,
        description
    )

    if success:
        print("\n" + "="*60)
        print("TEST COMPLETED")
        print("="*60)
        print("\nCheck results in database:")
        print("  python view_rejected_leads.py --stats")
        print("  python view_succeeded_leads.py")


if __name__ == '__main__':
    main()
