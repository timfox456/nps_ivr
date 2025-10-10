from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET
import json


def fake_llm_response(text, state):
    # Simulate extracting first name and asking for last name
    extracted = {"first_name": "Alex"} if "alex" in text.lower() else {}
    next_q = "What is your last name?"
    return extracted, next_q


@patch("app.llm.extract_and_prompt", side_effect=fake_llm_response)
def test_voice_initial_gather(mock_extract, client):
    res = client.post("/twilio/voice", data={"CallSid": "CA1", "From": "+1", "To": "+1"})
    assert res.status_code == 200
    body = res.text
    assert "<Gather" in body
    assert "Welcome to National Powersports Auctions" in body


@patch("app.llm.extract_and_prompt", side_effect=fake_llm_response)
def test_voice_collect_prompts_next_question(mock_extract, client):
    res = client.post("/twilio/voice/collect", data={"CallSid": "CA2", "From": "+1", "To": "+1", "SpeechResult": "My name is Alex"})
    assert res.status_code == 200
    body = res.text
    assert "<Gather" in body
    assert "What is your last name?" in body


@patch("app.main.get_or_create_session")
@patch("app.main.process_turn")
@patch("app.main.create_lead")
def test_voice_completion_hangup(mock_create_lead, mock_process_turn, mock_get_session, client):
    # Mock the session - start with phone and email already confirmed
    mock_session = MagicMock()
    mock_session.status = "open"
    mock_session.state = {
        "phone": "(555) 123-4567",  # Already confirmed
        "email": "test@example.com",  # Already confirmed
    }
    mock_get_session.return_value = mock_session

    # Mock the process_turn function to return a completed state
    # Since phone and email are already in state, process_turn won't add them again
    all_fields = {
        "first_name": "A",
        "last_name": "B",
        "address": "1 st",
        "phone": "(555) 123-4567",  # Same as before
        "email": "test@example.com",  # Same as before
        "vehicle_make": "Honda",
        "vehicle_model": "CB",
        "vehicle_year": "2020",
    }
    mock_process_turn.return_value = (all_fields, "", True)

    # Send a message to trigger the completion logic
    res = client.post("/twilio/voice/collect", data={"CallSid": "CA3", "From": "+1", "To": "+1", "SpeechResult": "complete"})
    assert res.status_code == 200

    # Check that create_lead was called
    mock_create_lead.assert_called_once()
