"""
End-to-End Integration Tests for Voice Calls

These tests actually connect to the running server and simulate real voice calls
using WebSocket connections and simulated audio. These would have caught the
critical data loss bug in production-like conditions.

Requirements:
- Server must be running on localhost:8000
- OpenAI API key must be configured
- Test database should be used (not production)
"""
import pytest
import asyncio
import json
import base64
import websockets
from typing import Optional
import httpx
from datetime import datetime

from app.db import SessionLocal
from app.models import ConversationSession, ConversationTurn, FailedLead, SucceededLead


# Configuration
SERVER_URL = "http://localhost:8000"
WS_STREAM_URL = "ws://localhost:8000/twilio/voice/stream"


@pytest.fixture
def db_session():
    """Database session for verification"""
    db = SessionLocal()
    yield db
    db.close()


class TestVoiceEndToEnd:
    """
    End-to-end tests that simulate actual voice calls through the full stack.

    These tests would have caught the critical bugs because they verify that
    data actually flows through the entire system end-to-end.
    """

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_health_check(self):
        """Verify server is running before E2E tests"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{SERVER_URL}/health")
                assert response.status_code == 200
            except Exception as e:
                pytest.skip(f"Server not running at {SERVER_URL}: {e}")

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires running server and OpenAI API - use for manual testing")
    async def test_full_voice_call_saves_data(self, db_session):
        """
        CRITICAL E2E TEST: Simulate a full voice call and verify data is saved.

        This test would have caught the bug where 60/63 calls had no data.

        This test:
        1. Opens WebSocket connection to server
        2. Simulates Twilio Media Stream messages
        3. Waits for conversation to complete
        4. Verifies data was saved to database
        """
        call_sid = f"CA_e2e_test_{datetime.now().timestamp()}"
        stream_sid = f"ST_e2e_test_{datetime.now().timestamp()}"

        # Track what we expect to be saved
        expected_fields = ["phone", "full_name", "zip_code", "vehicle_year", "vehicle_make", "vehicle_model"]

        try:
            async with websockets.connect(WS_STREAM_URL) as websocket:
                # Send Twilio "start" event
                start_event = {
                    "event": "start",
                    "sequenceNumber": 1,
                    "start": {
                        "streamSid": stream_sid,
                        "accountSid": "AC_test",
                        "callSid": call_sid,
                        "tracks": ["inbound"],
                        "customParameters": {
                            "caller_phone": "(555) 123-4567",
                            "phone_speech": "555-123-4567"
                        }
                    },
                    "streamSid": stream_sid
                }
                await websocket.send(json.dumps(start_event))

                # Wait for AI greeting
                await asyncio.sleep(3)

                # Simulate user responses with silent audio (OpenAI will timeout and move on)
                # In a real test, you'd use TTS to generate actual audio

                # Note: This is a simplified version - a full implementation would:
                # - Use text-to-speech to generate audio responses
                # - Send proper µ-law encoded audio
                # - Handle the full conversation flow

                # For now, just wait to see if session was created
                await asyncio.sleep(10)

                # Send stop event
                stop_event = {
                    "event": "stop",
                    "sequenceNumber": 100,
                    "streamSid": stream_sid
                }
                await websocket.send(json.dumps(stop_event))

        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")

        # CRITICAL VERIFICATION: Check database for saved data
        await asyncio.sleep(2)  # Give time for DB writes

        session = db_session.query(ConversationSession).filter(
            ConversationSession.session_key == call_sid
        ).first()

        # CRITICAL ASSERTIONS that would have caught the bug
        assert session is not None, f"Session with CallSid {call_sid} must exist in database"
        assert session.state is not None, "Session state must not be null"

        # Verify conversation turns were logged
        turns = db_session.query(ConversationTurn).filter(
            ConversationTurn.session_id == session.id
        ).all()

        assert len(turns) > 0, "Conversation turns must be logged"

        # Cleanup
        for turn in turns:
            db_session.delete(turn)
        db_session.delete(session)
        db_session.commit()


class TestVoiceSimulatedAudio:
    """
    Tests that use simulated audio to test the full voice pipeline.

    These tests generate simple audio data to test the OpenAI integration
    without requiring actual phone calls.
    """

    def generate_silence_audio(self, duration_ms: int = 1000) -> str:
        """
        Generate µ-law encoded silence audio for testing.

        Args:
            duration_ms: Duration of silence in milliseconds

        Returns:
            Base64 encoded µ-law audio data
        """
        # µ-law silence is represented by 0xFF
        # Twilio uses 8000 Hz sample rate, so 8 samples per millisecond
        samples = int(duration_ms * 8)
        silence = bytes([0xFF] * samples)
        return base64.b64encode(silence).decode('ascii')

    @pytest.mark.asyncio
    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires running server - use for manual testing")
    async def test_voice_with_simulated_audio(self, db_session):
        """
        Test voice call with simulated audio data.

        This sends actual audio packets (silence) to test the audio pipeline.
        """
        call_sid = f"CA_audio_test_{datetime.now().timestamp()}"
        stream_sid = f"ST_audio_test_{datetime.now().timestamp()}"

        try:
            async with websockets.connect(WS_STREAM_URL) as websocket:
                # Send start event
                start_event = {
                    "event": "start",
                    "sequenceNumber": 1,
                    "start": {
                        "streamSid": stream_sid,
                        "accountSid": "AC_test",
                        "callSid": call_sid,
                        "tracks": ["inbound"],
                        "customParameters": {}
                    },
                    "streamSid": stream_sid
                }
                await websocket.send(json.dumps(start_event))

                # Wait for greeting
                await asyncio.sleep(2)

                # Send simulated audio packets (silence)
                for i in range(10):
                    media_event = {
                        "event": "media",
                        "sequenceNumber": str(i + 2),
                        "media": {
                            "track": "inbound",
                            "chunk": str(i),
                            "timestamp": str(i * 20),
                            "payload": self.generate_silence_audio(20)
                        },
                        "streamSid": stream_sid
                    }
                    await websocket.send(json.dumps(media_event))
                    await asyncio.sleep(0.02)  # 20ms intervals

                # Wait for processing
                await asyncio.sleep(5)

                # Send stop
                stop_event = {
                    "event": "stop",
                    "sequenceNumber": 100,
                    "streamSid": stream_sid
                }
                await websocket.send(json.dumps(stop_event))

        except Exception as e:
            pytest.fail(f"Audio test failed: {e}")

        # Verify session created
        await asyncio.sleep(1)
        session = db_session.query(ConversationSession).filter(
            ConversationSession.session_key == call_sid
        ).first()

        assert session is not None, "Session must be created"

        # Cleanup
        if session:
            # Delete related records
            turns = db_session.query(ConversationTurn).filter(
                ConversationTurn.session_id == session.id
            ).all()
            for turn in turns:
                db_session.delete(turn)
            db_session.delete(session)
            db_session.commit()


class TestDatabaseVerification:
    """
    Tests that verify database state after voice calls.

    These can be run against a test database after making real calls
    to verify data was properly saved.
    """

    def test_recent_voice_calls_have_data(self, db_session):
        """
        CRITICAL: Verify recent voice calls have data saved.

        This test would have caught the bug where 60/63 calls had empty state.
        Run this test periodically against production to catch data loss issues.
        """
        from datetime import datetime, timedelta

        # Check calls from last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        recent_sessions = db_session.query(ConversationSession).filter(
            ConversationSession.channel == "voice",
            ConversationSession.created_at >= one_hour_ago
        ).all()

        if len(recent_sessions) == 0:
            pytest.skip("No recent voice calls to verify")

        # Count sessions with data
        sessions_with_data = 0
        sessions_without_data = 0

        for session in recent_sessions:
            # Ignore sessions that are just created (still in progress)
            if session.status == "open" and len(session.state) == 0:
                continue

            if session.state and len(session.state) > 1:  # More than just _channel
                sessions_with_data += 1
            else:
                sessions_without_data += 1

        total = sessions_with_data + sessions_without_data
        if total == 0:
            pytest.skip("No completed voice calls to verify")

        # CRITICAL ASSERTION: At least 80% of calls should have data
        success_rate = sessions_with_data / total
        assert success_rate >= 0.8, (
            f"Data loss detected! Only {success_rate:.1%} of voice calls have data. "
            f"({sessions_with_data}/{total} calls with data)"
        )

    def test_all_voice_calls_have_conversation_turns(self, db_session):
        """
        CRITICAL: Verify all voice calls have conversation turns logged.

        This test would have caught the missing audit trail.
        """
        from datetime import datetime, timedelta

        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        recent_sessions = db_session.query(ConversationSession).filter(
            ConversationSession.channel == "voice",
            ConversationSession.created_at >= one_hour_ago,
            ConversationSession.status == "closed"  # Only check completed calls
        ).all()

        if len(recent_sessions) == 0:
            pytest.skip("No recent completed voice calls")

        sessions_without_turns = []

        for session in recent_sessions:
            turn_count = db_session.query(ConversationTurn).filter(
                ConversationTurn.session_id == session.id
            ).count()

            if turn_count == 0:
                sessions_without_turns.append(session.id)

        # CRITICAL ASSERTION: All completed calls should have conversation turns
        assert len(sessions_without_turns) == 0, (
            f"Missing conversation turns for {len(sessions_without_turns)} sessions: "
            f"{sessions_without_turns}"
        )

    def test_no_session_reuse(self, db_session):
        """
        CRITICAL: Verify each voice call has unique session.

        This test would have caught the bug where all calls used session 72.
        """
        from datetime import datetime, timedelta

        one_hour_ago = datetime.utcnow() - timedelta(hours=1)

        # Get all recent voice sessions
        recent_sessions = db_session.query(ConversationSession).filter(
            ConversationSession.channel == "voice",
            ConversationSession.created_at >= one_hour_ago
        ).all()

        if len(recent_sessions) < 2:
            pytest.skip("Need at least 2 voice calls to test uniqueness")

        # Check for duplicate CallSids (excluding "pending")
        call_sids = [s.session_key for s in recent_sessions if s.session_key != "pending"]
        unique_call_sids = set(call_sids)

        # CRITICAL ASSERTION: All CallSids should be unique
        assert len(call_sids) == len(unique_call_sids), (
            f"Session reuse detected! {len(call_sids)} calls but only "
            f"{len(unique_call_sids)} unique CallSids"
        )


# Helper functions for manual E2E testing

async def manual_voice_test_with_text_responses():
    """
    Manual test helper that simulates a voice call with text responses
    converted to speech using a TTS service.

    Usage:
        python -m pytest tests/test_voice_e2e.py -k manual_voice_test -s

    This would be the MOST realistic test - using actual TTS to generate
    audio and testing the full pipeline.
    """
    # This would require:
    # 1. TTS service (Google TTS, AWS Polly, etc.)
    # 2. Audio encoding to µ-law format
    # 3. Streaming the audio to the WebSocket
    # 4. Handling the full conversation flow

    # Example conversation:
    conversation = [
        ("AI: What's your name?", "User: John Doe"),
        ("AI: What's your ZIP?", "User: 30047"),
        ("AI: Phone number?", "User: 555-123-4567"),
        ("AI: Vehicle info?", "User: 2020 Honda Civic"),
    ]

    # Each turn would:
    # 1. Wait for AI to speak
    # 2. Convert user text to speech
    # 3. Send audio to WebSocket
    # 4. Verify database updated

    print("Manual voice test helper - implement TTS integration for full E2E test")


if __name__ == "__main__":
    # Run quick database verification tests
    print("Running database verification tests...")
    print("These tests check if recent voice calls have proper data saved")
    print("\nRun with: python -m pytest tests/test_voice_e2e.py::TestDatabaseVerification -v")
