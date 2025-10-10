"""
Tests for caller ID detection and phone confirmation flow.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal, init_db
from app.models import ConversationSession


client = TestClient(app)


def fake_llm_response(text, state):
    """Fake LLM that extracts simple patterns."""
    extracted = {}
    if "john" in text.lower():
        extracted["first_name"] = "John"
    if "jane" in text.lower():
        extracted["first_name"] = "Jane"
    next_q = "What is your last name?"
    return extracted, next_q


@patch("app.llm.extract_and_prompt", side_effect=fake_llm_response)
def test_sms_auto_populates_phone_from_caller_id(mock_extract):
    """Test that SMS automatically populates phone from caller ID."""
    init_db()

    # Simulate SMS with valid caller ID
    response = client.post(
        "/twilio/sms",
        data={
            "From": "+15552234567",  # Valid phone number
            "To": "+16198530829",
            "Body": "John",
            "SmsSid": "SM_test_caller_id_123",
        },
    )

    assert response.status_code == 200
    assert "<?xml version" in response.text

    # Check database to verify phone was pre-populated
    # Use a fresh database session to avoid stale data
    db = SessionLocal()
    try:
        # Expunge all objects and query fresh
        db.expire_all()
        session = (
            db.query(ConversationSession)
            .filter(ConversationSession.session_key == "SM_test_caller_id_123")
            .first()
        )
        assert session is not None
        # Refresh to get latest data from database
        db.refresh(session)
        # Phone should be automatically populated from caller ID
        assert session.state.get("phone") == "(555) 223-4567"
        # First name should also be captured
        assert session.state.get("first_name") == "John"
    finally:
        db.close()


@patch("app.llm.extract_and_prompt", side_effect=fake_llm_response)
def test_sms_skips_invalid_caller_id(mock_extract):
    """Test that SMS doesn't populate phone from invalid caller ID."""
    init_db()

    # Simulate SMS with invalid caller ID (all same digits)
    response = client.post(
        "/twilio/sms",
        data={
            "From": "+15555555555",  # Invalid (all same digits)
            "To": "+16198530829",
            "Body": "Jane",
            "SmsSid": "SM_test_invalid_caller_123",
        },
    )

    assert response.status_code == 200

    # Check database - phone should NOT be pre-populated
    db = SessionLocal()
    try:
        db.expire_all()
        session = (
            db.query(ConversationSession)
            .filter(ConversationSession.session_key == "SM_test_invalid_caller_123")
            .first()
        )
        assert session is not None
        db.refresh(session)
        # Phone should NOT be populated from invalid caller ID
        assert "phone" not in session.state or session.state.get("phone") is None
        assert session.state.get("first_name") == "Jane"
    finally:
        db.close()


def test_voice_asks_phone_confirmation_with_valid_caller_id():
    """Test that voice call asks to confirm phone number from caller ID."""
    init_db()

    # Initial voice call with valid caller ID
    response = client.post(
        "/twilio/voice",
        data={
            "CallSid": "CA_test_confirm_123",
            "From": "+15552234567",  # Valid phone
            "To": "+16198530829",
        },
    )

    assert response.status_code == 200
    assert "<?xml version" in response.text
    # Should ask for confirmation
    assert "555-223-4567" in response.text
    assert "Is this the best number to reach you" in response.text or "best number" in response.text.lower()


def test_voice_skips_confirmation_with_invalid_caller_id():
    """Test that voice call skips phone confirmation with no/invalid caller ID."""
    init_db()

    # Initial voice call with invalid caller ID
    response = client.post(
        "/twilio/voice",
        data={
            "CallSid": "CA_test_no_confirm_123",
            "From": "unknown",  # No caller ID
            "To": "+16198530829",
        },
    )

    assert response.status_code == 200
    # Should NOT ask for phone confirmation
    assert "555" not in response.text
    # Should ask for first name instead
    assert "first name" in response.text.lower()


def test_voice_confirmation_yes_saves_phone():
    """Test that saying 'yes' to phone confirmation saves the phone number."""
    init_db()

    # Setup: Create session with pending phone
    db = SessionLocal()
    try:
        session = ConversationSession(
            channel="voice",
            session_key="CA_test_yes_456",
            from_number="+15552234567",
            to_number="+16198530829",
            state={"_pending_phone": "(555) 223-4567"},
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    finally:
        db.close()

    # User says "yes"
    response = client.post(
        "/twilio/voice/collect",
        data={
            "CallSid": "CA_test_yes_456",
            "From": "+15552234567",
            "To": "+16198530829",
            "SpeechResult": "yes",
        },
    )

    assert response.status_code == 200
    # Should confirm and ask for first name
    assert "first name" in response.text.lower()
    # Should not have <Hangup/> since we're still in the flow
    assert "<Hangup" not in response.text


def test_voice_confirmation_no_asks_for_phone():
    """Test that saying 'no' to phone confirmation asks for new phone number."""
    init_db()

    # Setup: Create session with pending phone
    db = SessionLocal()
    try:
        session = ConversationSession(
            channel="voice",
            session_key="CA_test_no_789",
            from_number="+15552234567",
            to_number="+16198530829",
            state={"_pending_phone": "(555) 223-4567"},
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    finally:
        db.close()

    # User says "no"
    response = client.post(
        "/twilio/voice/collect",
        data={
            "CallSid": "CA_test_no_789",
            "From": "+15552234567",
            "To": "+16198530829",
            "SpeechResult": "no",
        },
    )

    assert response.status_code == 200
    # Should ask for phone number
    assert "phone" in response.text.lower()
    # Should not ask for first name yet
    assert "first name" not in response.text.lower()


def test_voice_confirmation_unclear_response():
    """Test that unclear response to phone confirmation prompts again."""
    init_db()

    # Setup: Create session with pending phone
    db = SessionLocal()
    try:
        session = ConversationSession(
            channel="voice",
            session_key="CA_test_unclear_123",
            from_number="+15552234567",
            to_number="+16198530829",
            state={"_pending_phone": "(555) 223-4567"},
        )
        db.add(session)
        db.commit()
    finally:
        db.close()

    # User says something unclear
    response = client.post(
        "/twilio/voice/collect",
        data={
            "CallSid": "CA_test_unclear_123",
            "From": "+15552234567",
            "To": "+16198530829",
            "SpeechResult": "maybe later",
        },
    )

    assert response.status_code == 200
    # Should ask again
    assert "yes or no" in response.text.lower()

    # Verify pending phone is still there
    db = SessionLocal()
    try:
        session = (
            db.query(ConversationSession)
            .filter(ConversationSession.session_key == "CA_test_unclear_123")
            .first()
        )
        assert session.state.get("_pending_phone") == "(555) 223-4567"
        assert "phone" not in session.state or session.state.get("phone") is None
    finally:
        db.close()
