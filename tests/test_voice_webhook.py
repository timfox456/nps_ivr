from unittest.mock import patch


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


@patch("app.salesforce.create_lead", side_effect=lambda p: "LEAD42")
@patch("app.llm.process_turn", return_value=({
    "first_name": "A",
    "last_name": "B",
    "address": "1 st",
    "phone": "+1",
    "email": "a@b.com",
    "vehicle_make": "Honda",
    "vehicle_model": "CB",
    "vehicle_year": "2020",
}, "", True))
def test_voice_completion_hangup(mock_turn, mock_sf, client):
    res = client.post("/twilio/voice/collect", data={"CallSid": "CA3", "From": "+1", "To": "+1", "SpeechResult": "complete"})
    assert res.status_code == 200
    body = res.text
    assert "Thank you." in body or "Thank you" in body
    assert "<Hangup" in body or "</Hangup>" in body or "hangup" in body.lower()
    mock_sf.assert_called()
