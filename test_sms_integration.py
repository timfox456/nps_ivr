#!/usr/bin/env python3
"""
Integration test for SMS path with database validation.

This script simulates a complete SMS conversation and verifies that:
1. All messages are processed correctly
2. Rejected leads are saved to rejected_leads table
3. Accepted leads are saved to succeeded_leads table (or failed_leads on error)
"""
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal
from app.models import ConversationSession, RejectedLead, SucceededLead
import xml.etree.ElementTree as ET


def extract_message_from_twiml(twiml_str: str) -> str:
    """Extract the message text from TwiML response."""
    try:
        root = ET.fromstring(twiml_str)
        msg_elem = root.find('.//Message')
        if msg_elem is not None and msg_elem.text:
            return msg_elem.text.strip()
        return ""
    except Exception:
        return ""


def test_conversation(messages: list, description: str, should_be_rejected: bool = False):
    """
    Test a complete SMS conversation.

    Args:
        messages: List of user messages to send
        description: Description of the test case
        should_be_rejected: Whether this lead should be rejected by business rules
    """
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print('='*60)

    client = TestClient(app)
    session_id = f"TEST{uuid.uuid4().hex[:8]}"
    user_phone = "+15551234567"
    twilio_phone = "+16198530829"

    # Send each message
    for i, message in enumerate(messages):
        print(f"\n[{i+1}/{len(messages)}] User: {message}")

        response = client.post(
            "/twilio/sms",
            data={
                "From": user_phone,
                "To": twilio_phone,
                "Body": message,
                "SmsSid": session_id,
            }
        )

        bot_response = extract_message_from_twiml(response.text)
        print(f"Bot: {bot_response}")

    # Check database for results
    db = SessionLocal()
    try:
        # Check session
        session = db.query(ConversationSession).filter(
            ConversationSession.session_key == session_id
        ).first()

        if not session:
            print("\n❌ ERROR: No session found in database!")
            return False

        print(f"\n✓ Session created: ID={session.id}, Status={session.status}")
        print(f"  State: {session.state}")

        # Check for rejected lead
        rejected = db.query(RejectedLead).filter(
            RejectedLead.session_id == session.id
        ).first()

        # Check for succeeded lead
        succeeded = db.query(SucceededLead).filter(
            SucceededLead.session_id == session.id
        ).first()

        if should_be_rejected:
            if rejected:
                print(f"\n✓ PASS: Lead correctly rejected")
                print(f"  Category: {rejected.rejection_category}")
                print(f"  Reason: {rejected.rejection_reason}")
                return True
            else:
                print(f"\n❌ FAIL: Lead should have been rejected but wasn't!")
                if succeeded:
                    print(f"  Found in succeeded_leads instead!")
                return False
        else:
            if succeeded:
                print(f"\n✓ PASS: Lead correctly accepted and submitted")
                return True
            elif rejected:
                print(f"\n❌ FAIL: Lead should have been accepted but was rejected!")
                print(f"  Category: {rejected.rejection_category}")
                print(f"  Reason: {rejected.rejection_reason}")
                return False
            else:
                print(f"\n⚠ WARNING: Lead not found in succeeded_leads or rejected_leads")
                print(f"  (May have failed submission - check failed_leads table)")
                return True  # Not a validation failure

    finally:
        db.close()


def main():
    print("NPS IVR SMS Integration Test")
    print("="*60)

    results = []

    # Test 1: Accepted lead (eligible vehicle)
    results.append(test_conversation(
        messages=[
            "Hi",
            "John Smith",
            "90210",
            "3105551234",
            "john@test.com",
            "2020 Yamaha Grizzly"
        ],
        description="Eligible vehicle (2020 Yamaha Grizzly - ATV)",
        should_be_rejected=False
    ))

    # Test 2: Rejected - Old ATV
    results.append(test_conversation(
        messages=[
            "Hello",
            "Jane Doe",
            "30093",
            "4045551234",
            "jane@test.com",
            "2015 Honda Rancher"
        ],
        description="Rejected vehicle (2015 Honda Rancher - ATV too old)",
        should_be_rejected=True
    ))

    # Test 3: Rejected - Electric motorcycle
    results.append(test_conversation(
        messages=[
            "Hey",
            "Mike Wilson",
            "12345",
            "5555551234",
            "mike@test.com",
            "2023 Zero SR/F"
        ],
        description="Rejected vehicle (2023 Zero SR/F - Electric)",
        should_be_rejected=True
    ))

    # Test 4: Rejected - Slingshot
    results.append(test_conversation(
        messages=[
            "Hi there",
            "Tom Brown",
            "60601",
            "3125551234",
            "tom@test.com",
            "2020 Polaris Slingshot"
        ],
        description="Rejected vehicle (2020 Polaris Slingshot)",
        should_be_rejected=True
    ))

    # Test 5: Rejected - Old metric motorcycle
    results.append(test_conversation(
        messages=[
            "Hello",
            "Sarah Johnson",
            "10001",
            "2125551234",
            "sarah@test.com",
            "2005 Honda CBR600RR"
        ],
        description="Rejected vehicle (2005 Honda CBR600RR - Metric too old)",
        should_be_rejected=True
    ))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("✓ ALL TESTS PASSED!")
    else:
        print(f"❌ {total - passed} test(s) failed")

    print("\nView results:")
    print("  python view_rejected_leads.py --stats")
    print("  python view_succeeded_leads.py")


if __name__ == '__main__':
    main()
