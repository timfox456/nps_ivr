#!/usr/bin/env python3
"""
Automated test for voice call flow without requiring microphone.
Tests the phone confirmation logic fix.
"""

import sys
import time
import requests

BASE_URL = "http://localhost:8000"


def extract_say_text(twiml):
    """Extract text from <Say> tags in TwiML."""
    import re
    matches = re.findall(r'<Say[^>]*>(.*?)</Say>', twiml, re.DOTALL | re.IGNORECASE)
    if matches:
        text = ' '.join(matches)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()
    return None


def test_voice_flow():
    """Test the complete voice flow with phone confirmation."""
    call_sid = f"TEST_CALL_{int(time.time())}"
    from_number = "+17203811084"
    to_number = "+16198530829"

    print("\n" + "="*60)
    print("Testing Voice Call Flow with Phone Confirmation Fix")
    print("="*60 + "\n")

    # Step 1: Initial call - should ask for phone confirmation
    print("Step 1: Initial call...")
    response = requests.post(
        f"{BASE_URL}/twilio/voice",
        data={
            "CallSid": call_sid,
            "From": from_number,
            "To": to_number,
        }
    )

    if response.status_code != 200:
        print(f"❌ FAILED: Initial call returned {response.status_code}")
        return False

    twiml = response.text
    message = extract_say_text(twiml)
    print(f"IVR: {message}")

    if "calling from" not in message.lower() or "720-381-1084" not in message:
        print(f"❌ FAILED: Expected phone confirmation prompt")
        return False

    print("✓ Phone confirmation prompt received\n")

    # Step 2: User says "yes" to confirm phone
    print("Step 2: User confirms phone number with 'yes'...")
    response = requests.post(
        f"{BASE_URL}/twilio/voice/collect",
        data={
            "CallSid": call_sid,
            "From": from_number,
            "To": to_number,
            "SpeechResult": "yes",
        }
    )

    if response.status_code != 200:
        print(f"❌ FAILED: Confirmation returned {response.status_code}")
        return False

    twiml = response.text
    message = extract_say_text(twiml)
    print(f"IVR: {message}")

    if "first name" not in message.lower():
        print(f"❌ FAILED: Expected to ask for first name, got: {message}")
        return False

    print("✓ Phone confirmed, asking for first name\n")

    # Step 3: User provides first name "Timothy"
    print("Step 3: User provides first name 'Timothy'...")
    response = requests.post(
        f"{BASE_URL}/twilio/voice/collect",
        data={
            "CallSid": call_sid,
            "From": from_number,
            "To": to_number,
            "SpeechResult": "Timothy",
        }
    )

    if response.status_code != 200:
        print(f"❌ FAILED: First name submission returned {response.status_code}")
        return False

    twiml = response.text
    message = extract_say_text(twiml)
    print(f"IVR: {message}")

    # This is the critical test - should NOT loop back to phone confirmation
    if "calling from" in message.lower() or "best number" in message.lower():
        print(f"❌ FAILED: Looped back to phone confirmation! Message: {message}")
        return False

    if "last name" not in message.lower():
        print(f"❌ FAILED: Expected to ask for last name, got: {message}")
        return False

    print("✓ First name accepted, asking for last name\n")

    # Step 4: User provides last name "Fox"
    print("Step 4: User provides last name 'Fox'...")
    response = requests.post(
        f"{BASE_URL}/twilio/voice/collect",
        data={
            "CallSid": call_sid,
            "From": from_number,
            "To": to_number,
            "SpeechResult": "Fox",
        }
    )

    if response.status_code != 200:
        print(f"❌ FAILED: Last name submission returned {response.status_code}")
        return False

    twiml = response.text
    message = extract_say_text(twiml)
    print(f"IVR: {message}")

    # Should ask for next field (address/state)
    if "state" not in message.lower() and "address" not in message.lower():
        print(f"❌ FAILED: Expected to ask for state/address, got: {message}")
        return False

    print("✓ Last name accepted, asking for state\n")

    print("="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print("\nThe phone confirmation loop bug is FIXED!")
    print("- Phone number was confirmed from caller ID")
    print("- First name was accepted without looping back")
    print("- Flow continued normally to collect remaining fields")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_voice_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
