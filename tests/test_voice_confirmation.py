"""
Tests for voice confirmation flows for phone numbers and email addresses.
"""
from unittest.mock import patch, MagicMock


class TestPhoneNumberConfirmation:
    """Tests for phone number confirmation in voice workflow."""

    @patch("app.main.get_or_create_session")
    @patch("app.main.process_turn")
    def test_phone_triggers_confirmation(self, mock_process_turn, mock_get_session, client):
        """When a phone number is extracted, it should trigger a confirmation prompt."""
        # Mock the session with no phone yet
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "last_name": "Doe"
        }
        mock_get_session.return_value = mock_session

        # Mock process_turn to extract a phone number
        new_state = {
            "first_name": "John",
            "last_name": "Doe",
            "phone": "(555) 123-4567"
        }
        mock_process_turn.return_value = (new_state, "What is your email?", False)

        # Send a message that would extract phone
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_PHONE_TEST",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "555-123-4567"
        })

        assert res.status_code == 200
        body = res.text
        # Should ask for confirmation
        assert "I heard your phone number is" in body
        assert "555, 123, 4567" in body
        assert "Is that correct" in body

    @patch("app.main.get_or_create_session")
    def test_phone_confirmation_yes_saves_number(self, mock_get_session, client):
        """When user confirms phone with 'yes', it should be saved."""
        # Mock the session with pending phone confirmation
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "_pending_phone_confirm": "(555) 123-4567",
            "_pending_phone_confirm_speech": "555, 123, 4567"
        }
        mock_get_session.return_value = mock_session

        # User confirms with "yes"
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_PHONE_YES",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "yes"
        })

        assert res.status_code == 200
        body = res.text
        # Should proceed to next question
        assert "<Gather" in body
        assert "Got it" in body

        # Verify phone was saved in the mocked session
        assert mock_session.state["phone"] == "(555) 123-4567"
        assert "_pending_phone_confirm" not in mock_session.state

    @patch("app.main.get_or_create_session")
    def test_phone_confirmation_no_asks_again(self, mock_get_session, client):
        """When user rejects phone with 'no', it should ask for phone again."""
        # Mock the session with pending phone confirmation
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "_pending_phone_confirm": "(555) 123-4567",
            "_pending_phone_confirm_speech": "555, 123, 4567"
        }
        mock_get_session.return_value = mock_session

        # User rejects with "no"
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_PHONE_NO",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "no"
        })

        assert res.status_code == 200
        body = res.text
        # Should ask for phone number again
        assert "Sorry about that" in body
        assert "phone number again" in body

        # Verify pending phone was removed
        assert "_pending_phone_confirm" not in mock_session.state

    @patch("app.main.get_or_create_session")
    def test_phone_confirmation_unclear_repeats_question(self, mock_get_session, client):
        """When user response is unclear, it should repeat the confirmation question."""
        # Mock the session with pending phone confirmation
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "_pending_phone_confirm": "(555) 123-4567",
            "_pending_phone_confirm_speech": "555, 123, 4567"
        }
        mock_get_session.return_value = mock_session

        # User gives unclear response
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_PHONE_UNCLEAR",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "maybe"
        })

        assert res.status_code == 200
        body = res.text
        # Should repeat the confirmation question
        assert "I didn't catch that" in body
        assert "555, 123, 4567" in body
        assert "Is that correct" in body


class TestEmailConfirmation:
    """Tests for email confirmation in voice workflow."""

    @patch("app.main.get_or_create_session")
    @patch("app.main.process_turn")
    def test_email_triggers_confirmation(self, mock_process_turn, mock_get_session, client):
        """When an email is extracted, it should trigger a confirmation prompt."""
        # Mock the session with no email yet
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "last_name": "Doe",
            "phone": "(555) 123-4567"
        }
        mock_get_session.return_value = mock_session

        # Mock process_turn to extract an email
        new_state = {
            "first_name": "John",
            "last_name": "Doe",
            "phone": "(555) 123-4567",
            "email": "john@example.com"
        }
        mock_process_turn.return_value = (new_state, "What is the vehicle make?", False)

        # Send a message that would extract email
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_EMAIL_TEST",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "john at example dot com"
        })

        assert res.status_code == 200
        body = res.text
        # Should ask for confirmation
        assert "I heard your email is" in body
        assert "john at example dot com" in body
        assert "Is that correct" in body

    @patch("app.main.get_or_create_session")
    def test_email_confirmation_yes_saves_email(self, mock_get_session, client):
        """When user confirms email with 'yes', it should be saved."""
        # Mock the session with pending email confirmation
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "phone": "(555) 123-4567",
            "_pending_email": "john@example.com",
            "_pending_email_speech": "john at example dot com"
        }
        mock_get_session.return_value = mock_session

        # User confirms with "yes"
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_EMAIL_YES",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "yes"
        })

        assert res.status_code == 200
        body = res.text
        # Should proceed to next question
        assert "<Gather" in body
        assert "Perfect" in body

        # Verify email was saved in the mocked session
        assert mock_session.state["email"] == "john@example.com"
        assert "_pending_email" not in mock_session.state

    @patch("app.main.get_or_create_session")
    def test_email_confirmation_no_asks_again(self, mock_get_session, client):
        """When user rejects email with 'no', it should ask for email again."""
        # Mock the session with pending email confirmation
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "phone": "(555) 123-4567",
            "_pending_email": "wrong@example.com",
            "_pending_email_speech": "wrong at example dot com"
        }
        mock_get_session.return_value = mock_session

        # User rejects with "no"
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_EMAIL_NO",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "no"
        })

        assert res.status_code == 200
        body = res.text
        # Should ask for email again
        assert "Sorry about that" in body
        assert "email address again" in body
        assert "saying 'at' for the at symbol" in body

        # Verify pending email was removed
        assert "_pending_email" not in mock_session.state

    @patch("app.main.get_or_create_session")
    def test_email_confirmation_unclear_repeats_question(self, mock_get_session, client):
        """When user response is unclear, it should repeat the confirmation question."""
        # Mock the session with pending email confirmation
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "phone": "(555) 123-4567",
            "_pending_email": "john@example.com",
            "_pending_email_speech": "john at example dot com"
        }
        mock_get_session.return_value = mock_session

        # User gives unclear response
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_EMAIL_UNCLEAR",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "what was that"
        })

        assert res.status_code == 200
        body = res.text
        # Should repeat the confirmation question
        assert "I didn't catch that" in body
        assert "john at example dot com" in body
        assert "Is that correct" in body


class TestConfirmationIntegration:
    """Integration tests for the confirmation flows."""

    @patch("app.main.get_or_create_session")
    @patch("app.main.process_turn")
    def test_phone_does_not_trigger_confirmation_if_already_set(self, mock_process_turn, mock_get_session, client):
        """If phone is already in state, it should not trigger confirmation again."""
        # Mock the session with phone already set
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "phone": "(555) 123-4567"  # Already confirmed
        }
        mock_get_session.return_value = mock_session

        # Mock process_turn to return state with same phone
        new_state = {
            "first_name": "John",
            "phone": "(555) 123-4567",  # Same as before
            "last_name": "Doe"
        }
        mock_process_turn.return_value = (new_state, "What is your email?", False)

        # Send a message
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_NO_CONFIRM",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "my last name is Doe"
        })

        assert res.status_code == 200
        body = res.text
        # Should NOT ask for phone confirmation
        assert "I heard your phone number is" not in body
        # Should ask next question
        assert "What is your email" in body

    @patch("app.main.get_or_create_session")
    @patch("app.main.process_turn")
    def test_email_does_not_trigger_confirmation_if_already_set(self, mock_process_turn, mock_get_session, client):
        """If email is already in state, it should not trigger confirmation again."""
        # Mock the session with email already set
        mock_session = MagicMock()
        mock_session.status = "open"
        mock_session.state = {
            "first_name": "John",
            "phone": "(555) 123-4567",
            "email": "john@example.com"  # Already confirmed
        }
        mock_get_session.return_value = mock_session

        # Mock process_turn to return state with same email
        new_state = {
            "first_name": "John",
            "phone": "(555) 123-4567",
            "email": "john@example.com",  # Same as before
            "address": "CA"
        }
        mock_process_turn.return_value = (new_state, "What is the vehicle make?", False)

        # Send a message
        res = client.post("/twilio/voice/collect", data={
            "CallSid": "CA_NO_EMAIL_CONFIRM",
            "From": "+1",
            "To": "+1",
            "SpeechResult": "California"
        })

        assert res.status_code == 200
        body = res.text
        # Should NOT ask for email confirmation
        assert "I heard your email is" not in body
        # Should ask next question
        assert "What is the vehicle make" in body
