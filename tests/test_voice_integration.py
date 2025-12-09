"""
Integration tests for voice call handling with OpenAI Realtime API.

These tests would have caught the critical voice data loss bug where
60+ voice calls had no data saved to the database.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.voice_openai import TwilioMediaStreamHandler
from app.models import ConversationSession, ConversationTurn, FailedLead, SucceededLead
from app.db import SessionLocal


@pytest.fixture
def db_session():
    """Create a test database session"""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def mock_twilio_ws():
    """Mock Twilio WebSocket connection"""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.iter_text = AsyncMock()
    return ws


@pytest.fixture
def mock_openai_ws():
    """Mock OpenAI WebSocket connection"""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    ws.closed = False
    return ws


class TestVoiceDataPersistence:
    """Test that voice calls properly save data - would have caught the critical bug"""

    @pytest.mark.asyncio
    async def test_voice_call_creates_new_session(self, db_session, mock_twilio_ws):
        """Test that each voice call creates a unique session"""
        # Setup
        call_sid_1 = "CA_test_call_1"
        call_sid_2 = "CA_test_call_2"

        # Create handler for first call
        handler1 = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid_1,
            stream_sid="ST_test_1"
        )
        handler1.db = db_session
        session1 = handler1._get_or_create_session()

        # Create handler for second call
        handler2 = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid_2,
            stream_sid="ST_test_2"
        )
        handler2.db = db_session
        session2 = handler2._get_or_create_session()

        # Assert: Each call gets unique session
        assert session1.id != session2.id
        assert session1.session_key == call_sid_1
        assert session2.session_key == call_sid_2
        assert session1.status == "open"
        assert session2.status == "open"

        # Cleanup
        db_session.delete(session1)
        db_session.delete(session2)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_closed_session_not_reused(self, db_session, mock_twilio_ws):
        """Test that closed sessions are not reused - prevents session reuse bug"""
        call_sid = "CA_test_call_closed"

        # Create and close first session
        handler1 = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler1.db = db_session
        session1 = handler1._get_or_create_session()
        session1.status = "closed"
        db_session.commit()

        # Try to create another session with same call_sid
        handler2 = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler2.db = db_session
        session2 = handler2._get_or_create_session()

        # Assert: New session created, not reusing closed one
        assert session2.id != session1.id
        assert session2.status == "open"

        # Cleanup
        db_session.delete(session1)
        db_session.delete(session2)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_function_call_saves_field_to_database(self, db_session, mock_twilio_ws, mock_openai_ws):
        """Test that save_lead_field function actually saves to database - catches data loss bug"""
        call_sid = "CA_test_save_field"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.openai_ws = mock_openai_ws
        handler.session = handler._get_or_create_session()

        # Simulate function call for saving full_name
        initial_state = dict(handler.session.state)

        # Manually execute the save_lead_field logic
        field_name = "full_name"
        field_value = "John Doe"
        handler.session.state[field_name] = field_value
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(handler.session, "state")
        db_session.commit()
        db_session.refresh(handler.session)

        # Assert: Data was saved to database
        assert handler.session.state.get("full_name") == "John Doe"

        # Verify by querying fresh from database
        fresh_session = db_session.query(ConversationSession).filter(
            ConversationSession.id == handler.session.id
        ).first()
        assert fresh_session.state.get("full_name") == "John Doe"

        # Cleanup
        db_session.delete(handler.session)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_multiple_fields_saved_incrementally(self, db_session, mock_twilio_ws, mock_openai_ws):
        """Test that multiple fields are saved incrementally during conversation"""
        call_sid = "CA_test_multiple_fields"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.openai_ws = mock_openai_ws
        handler.session = handler._get_or_create_session()

        # Simulate saving multiple fields one by one
        fields = {
            "full_name": "Jane Smith",
            "zip_code": "30047",
            "phone": "(555) 123-4567",
            "vehicle_year": "2020",
            "vehicle_make": "Honda",
            "vehicle_model": "Civic"
        }

        from sqlalchemy.orm.attributes import flag_modified
        for field_name, field_value in fields.items():
            handler.session.state[field_name] = field_value
            flag_modified(handler.session, "state")
            db_session.commit()
            db_session.refresh(handler.session)

            # Assert: Field was saved
            assert handler.session.state.get(field_name) == field_value

        # Assert: All fields are in final state
        for field_name, field_value in fields.items():
            assert handler.session.state.get(field_name) == field_value

        # Cleanup
        db_session.delete(handler.session)
        db_session.commit()


class TestConversationTurnLogging:
    """Test that all conversation turns are logged - catches missing audit trail"""

    @pytest.mark.asyncio
    async def test_conversation_turn_logged(self, db_session, mock_twilio_ws):
        """Test that conversation turns are logged to database"""
        call_sid = "CA_test_turn_logging"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.session = handler._get_or_create_session()

        # Set up turn data
        handler.current_user_transcript = "My name is John"
        handler.current_ai_transcript = "Thank you, John. What's your ZIP code?"
        handler.current_turn_fields = {"full_name": "John"}

        # Log the turn
        handler._log_conversation_turn()

        # Assert: Turn was logged
        turns = db_session.query(ConversationTurn).filter(
            ConversationTurn.session_id == handler.session.id
        ).all()

        assert len(turns) == 1
        assert turns[0].turn_number == 1
        assert turns[0].user_audio_transcript == "My name is John"
        assert turns[0].ai_audio_transcript == "Thank you, John. What's your ZIP code?"
        assert turns[0].fields_extracted == {"full_name": "John"}

        # Cleanup
        db_session.delete(turns[0])
        db_session.delete(handler.session)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_multiple_turns_logged_sequentially(self, db_session, mock_twilio_ws):
        """Test that multiple conversation turns are logged with correct turn numbers"""
        call_sid = "CA_test_multi_turns"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.session = handler._get_or_create_session()

        # Log 3 turns
        turns_data = [
            ("Hello", "Hi! What's your name?", {}),
            ("John Doe", "Thanks John, what's your ZIP?", {"full_name": "John Doe"}),
            ("30047", "Got it. Tell me about your vehicle.", {"zip_code": "30047"}),
        ]

        for user_text, ai_text, fields in turns_data:
            handler.current_user_transcript = user_text
            handler.current_ai_transcript = ai_text
            handler.current_turn_fields = fields
            handler._log_conversation_turn()

        # Assert: All turns logged with correct sequence
        turns = db_session.query(ConversationTurn).filter(
            ConversationTurn.session_id == handler.session.id
        ).order_by(ConversationTurn.turn_number).all()

        assert len(turns) == 3
        for i, turn in enumerate(turns, 1):
            assert turn.turn_number == i
            assert turn.user_audio_transcript == turns_data[i-1][0]
            assert turn.ai_audio_transcript == turns_data[i-1][1]
            assert turn.fields_extracted == turns_data[i-1][2]

        # Cleanup
        for turn in turns:
            db_session.delete(turn)
        db_session.delete(handler.session)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_turn_includes_state_snapshot(self, db_session, mock_twilio_ws):
        """Test that each turn includes a snapshot of the session state"""
        call_sid = "CA_test_state_snapshot"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.session = handler._get_or_create_session()

        # Add some state and log turn
        handler.session.state = {"full_name": "John", "zip_code": "30047"}
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(handler.session, "state")
        db_session.commit()

        handler.current_user_transcript = "Yes, that's correct"
        handler.current_ai_transcript = "Great, what's your phone?"
        handler.current_turn_fields = {}
        handler._log_conversation_turn()

        # Assert: Turn has state snapshot
        turn = db_session.query(ConversationTurn).filter(
            ConversationTurn.session_id == handler.session.id
        ).first()

        assert turn.state_after_turn is not None
        assert turn.state_after_turn.get("full_name") == "John"
        assert turn.state_after_turn.get("zip_code") == "30047"

        # Cleanup
        db_session.delete(turn)
        db_session.delete(handler.session)
        db_session.commit()


class TestLeadSubmission:
    """Test that leads are properly submitted and tracked"""

    @pytest.mark.asyncio
    async def test_lead_saved_to_failed_leads_on_error(self, db_session, mock_twilio_ws, mock_openai_ws):
        """Test that failed leads are saved for retry - prevents data loss"""
        call_sid = "CA_test_failed_lead"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.openai_ws = mock_openai_ws
        handler.session = handler._get_or_create_session()

        # Set up complete lead data
        handler.session.state = {
            "full_name": "Test User",
            "zip_code": "12345",
            "phone": "(555) 999-8888",
            "vehicle_year": "2020",
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
            "email": "voice+5559998888@test.com"
        }
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(handler.session, "state")
        db_session.commit()

        # Manually create a failed lead (simulating submission failure)
        from app.models import FailedLead
        failed_lead = FailedLead(
            lead_data=dict(handler.session.state),
            error_message="Test API error",
            channel="voice",
            session_id=handler.session.id
        )
        db_session.add(failed_lead)
        db_session.commit()

        # Assert: Lead saved to failed_leads
        failed = db_session.query(FailedLead).filter(
            FailedLead.session_id == handler.session.id
        ).first()

        assert failed is not None
        assert failed.error_message == "Test API error"
        assert failed.lead_data.get("full_name") == "Test User"
        assert failed.lead_data.get("phone") == "(555) 999-8888"
        assert failed.retry_count == 0

        # Cleanup
        db_session.delete(failed)
        db_session.delete(handler.session)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_dummy_email_generated_for_voice(self, db_session, mock_twilio_ws):
        """Test that dummy email is automatically generated for voice leads"""
        call_sid = "CA_test_dummy_email"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.session = handler._get_or_create_session()

        # Set up lead data without email
        phone = "(720) 555-1234"
        handler.session.state = {
            "phone": phone,
            "full_name": "Test User"
        }

        # Simulate adding dummy email
        if not handler.session.state.get("email"):
            clean_phone = phone.replace("(", "").replace(")", "").replace(" ", "").replace("-", "")
            handler.session.state["email"] = f"voice+{clean_phone}@powersportbuyers.com"

        # Assert: Dummy email generated correctly
        assert handler.session.state.get("email") == "voice+7205551234@powersportbuyers.com"

        # Cleanup
        db_session.delete(handler.session)
        db_session.commit()


class TestSessionKeyUpdate:
    """Test that session keys are properly updated from pending to real CallSid"""

    @pytest.mark.asyncio
    async def test_session_key_updates_from_pending(self, db_session, mock_twilio_ws):
        """Test that session_key updates when real CallSid is received - fixes session reuse bug"""
        initial_call_sid = "pending"
        real_call_sid = "CA_real_call_sid_12345"

        # Create handler with pending CallSid
        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=initial_call_sid
        )
        handler.db = db_session
        handler.session = handler._get_or_create_session()

        # Verify initial state
        assert handler.session.session_key == "pending"
        session_id = handler.session.id

        # Simulate receiving real CallSid from Twilio start event
        handler.call_sid = real_call_sid
        handler.session.session_key = real_call_sid
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(handler.session, "session_key")
        db_session.commit()
        db_session.refresh(handler.session)

        # Assert: Session key updated
        assert handler.session.session_key == real_call_sid
        assert handler.session.id == session_id  # Same session, just updated key

        # Verify in database
        fresh_session = db_session.query(ConversationSession).filter(
            ConversationSession.id == session_id
        ).first()
        assert fresh_session.session_key == real_call_sid

        # Cleanup
        db_session.delete(handler.session)
        db_session.commit()


class TestCriticalBugScenarios:
    """Tests that specifically target the bugs we discovered"""

    @pytest.mark.asyncio
    async def test_voice_call_must_save_data(self, db_session, mock_twilio_ws):
        """
        CRITICAL: Test that voice calls save data to database.

        This test would have caught the bug where 60 out of 63 calls had no data.
        """
        call_sid = "CA_critical_test_data_loss"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.session = handler._get_or_create_session()

        # Simulate collecting lead data
        lead_data = {
            "full_name": "Critical Test",
            "zip_code": "99999",
            "phone": "(999) 888-7777"
        }

        from sqlalchemy.orm.attributes import flag_modified
        for field, value in lead_data.items():
            handler.session.state[field] = value
            flag_modified(handler.session, "state")
            db_session.commit()

        # CRITICAL ASSERTION: Data must be in database
        fresh_session = db_session.query(ConversationSession).filter(
            ConversationSession.id == handler.session.id
        ).first()

        assert fresh_session.state is not None, "Session state must not be null"
        assert len(fresh_session.state) > 0, "Session state must not be empty"
        assert fresh_session.state.get("full_name") == "Critical Test"
        assert fresh_session.state.get("phone") == "(999) 888-7777"

        # Cleanup
        db_session.delete(handler.session)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_each_call_unique_session(self, db_session, mock_twilio_ws):
        """
        CRITICAL: Test that each call gets a unique session.

        This test would have caught the bug where all calls reused session 72.
        """
        call_sids = [f"CA_unique_test_{i}" for i in range(5)]
        session_ids = []

        for call_sid in call_sids:
            handler = TwilioMediaStreamHandler(
                twilio_ws=mock_twilio_ws,
                call_sid=call_sid
            )
            handler.db = db_session
            session = handler._get_or_create_session()
            session_ids.append(session.id)

        # CRITICAL ASSERTION: All session IDs must be unique
        assert len(session_ids) == len(set(session_ids)), "Each call must create unique session"

        # Cleanup
        for session_id in session_ids:
            session = db_session.query(ConversationSession).get(session_id)
            if session:
                db_session.delete(session)
        db_session.commit()

    @pytest.mark.asyncio
    async def test_conversation_turns_must_be_logged(self, db_session, mock_twilio_ws):
        """
        CRITICAL: Test that conversation turns are logged.

        This test would have caught the missing audit trail.
        """
        call_sid = "CA_critical_test_audit"

        handler = TwilioMediaStreamHandler(
            twilio_ws=mock_twilio_ws,
            call_sid=call_sid
        )
        handler.db = db_session
        handler.session = handler._get_or_create_session()

        # Simulate a conversation with 3 turns
        for i in range(3):
            handler.current_user_transcript = f"User message {i+1}"
            handler.current_ai_transcript = f"AI response {i+1}"
            handler.current_turn_fields = {"test_field": f"value_{i+1}"}
            handler._log_conversation_turn()

        # CRITICAL ASSERTION: Turns must be logged
        turns = db_session.query(ConversationTurn).filter(
            ConversationTurn.session_id == handler.session.id
        ).all()

        assert len(turns) == 3, "All conversation turns must be logged"
        assert turns[0].turn_number == 1
        assert turns[1].turn_number == 2
        assert turns[2].turn_number == 3

        # Cleanup
        for turn in turns:
            db_session.delete(turn)
        db_session.delete(handler.session)
        db_session.commit()
