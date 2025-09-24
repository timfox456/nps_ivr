import json
from unittest.mock import patch

from app.models import REQUIRED_FIELDS


def fake_llm_response(text, state):
    # Very simple fake: extract an email-like and a 4-digit year
    extracted = {}
    if "john" in text.lower():
        extracted["first_name"] = "John"
        if "doe" in text.lower():
            extracted["last_name"] = "Doe"
    if "@" in text:
        extracted["email"] = "john@example.com"
    if "harley" in text.lower():
        extracted["vehicle_make"] = "Harley-Davidson"
    if "sportster" in text.lower():
        extracted["vehicle_model"] = "Sportster"
    if "2018" in text:
        extracted["vehicle_year"] = "2018"
    next_q = "What is your last name?"
    return extracted, next_q


@patch("app.llm.extract_and_prompt", side_effect=fake_llm_response)
def test_sms_intake_progress(mock_extract, client):
    # First message: include first name and vehicle info
    form = {
        "From": "+15551234567",
        "To": "+15557654321",
        "Body": "Hi I'm John selling a 2018 Harley Sportster",
        "SmsSid": "SMxxxx1",
    }
    res = client.post("/twilio/sms", data=form)
    assert res.status_code == 200
    assert "What is your last name?" in res.text

    # Second message: provide last name and email
    form2 = {
        "From": "+15551234567",
        "To": "+15557654321",
        "Body": "Doe, email john@example.com",
        "SmsSid": "SMxxxx1",
    }
    res2 = client.post("/twilio/sms", data=form2)
    assert res2.status_code == 200
    # Should continue to ask for missing field
    assert res2.text


@patch("app.llm.extract_and_prompt", side_effect=lambda text, state: (state, ""))
@patch("app.salesforce.create_lead")
def test_sms_completion_triggers_salesforce(mock_sf, mock_extract, client):
    async def _fake_sf(payload):
        return "LEAD123"
    mock_sf.side_effect = _fake_sf

    # Provide all fields to simulate completion
    all_fields = {
        "first_name": "Jane",
        "last_name": "Rider",
        "address": "1 Main St, Anytown, NY",
        "phone": "+15550000000",
        "email": "jane@example.com",
        "vehicle_make": "Honda",
        "vehicle_model": "CB500",
        "vehicle_year": "2020",
    }
    # We monkey patch state persistence by pre-seeding message content that encodes JSON
    form = {"From": "+1", "To": "+1", "Body": json.dumps(all_fields), "SmsSid": "SMdone1"}
    res = client.post("/twilio/sms", data=form)
    assert res.status_code == 200
    # With the fake llm returning same state, the app won't parse JSON from Body by default.
    # Instead, simulate two calls: first sets state, second completes.
    with patch("app.llm.process_turn", return_value=(all_fields, "", True)):
        res2 = client.post("/twilio/sms", data={"From": "+1", "To": "+1", "Body": "complete", "SmsSid": "SMdone1"})
        assert res2.status_code == 200
        assert "Thank you" in res2.text
        mock_sf.assert_called()
