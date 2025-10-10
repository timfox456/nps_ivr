import json
import re
from typing import Dict, Any, Tuple
from openai import OpenAI
from .config import settings
from .models import missing_fields, FIELD_PRETTY
from .validation import validate_and_normalize_field, normalize_transcribed_email

_client: OpenAI | None = None

def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client

DEFAULT_QUESTIONS = {
    "first_name": "What is your first name?",
    "last_name": "What is your last name?",
    "address": "What state do you reside in?",
    "phone": "What is the best phone number to reach you?",
    "email": "What is your email address?",
    "vehicle_make": "What is the make of the vehicle?",
    "vehicle_model": "What is the model of the vehicle?",
    "vehicle_year": "What is the year of the vehicle?",
}

YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def normalize_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in fields.items():
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        if k == "vehicle_year":
            m = YEAR_RE.search(s)
            if m:
                s = m.group(1)
        out[k] = s
    return out


def extract_and_prompt(user_text: str, state: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    sys = (
        "You are a lead intake assistant for National Powersports Auctions (NPA), helping customers sell their powersports vehicles. "
        "From the user's message, extract any of these fields if present: first_name, last_name, address, phone, email, vehicle_make, vehicle_model, vehicle_year. "
        "IMPORTANT: For the 'address' field, we only need the STATE of residence. If the user provides a full address, extract only the state abbreviation or name. "
        "IMPORTANT: When the user provides a short direct answer (like just 'Smith' or 'John'), use the conversation context to infer which field they're answering. "
        "Look at the known_state to see what fields are still missing and what was likely just asked. "
        "For example, if last_name is missing and they say 'Smith', extract it as last_name: 'Smith'. "
        "IMPORTANT: For EMAIL addresses from voice input, common transcription patterns: "
        "'at' means '@', 'dot' means '.', 'underscore' means '_', 'dash' or 'hyphen' means '-'. "
        "Examples: 'tfox at yahoo dot com' = 'tfox@yahoo.com', 'john dot smith at gmail dot com' = 'john.smith@gmail.com'. "
        "Extract the email exactly as transcribed - validation will be handled separately. "
        "IMPORTANT: For PHONE numbers, extract all digits. Accept formats like (555) 123-4567, 555-123-4567, or 5551234567. "
        "IMPORTANT: For VEHICLE MAKE/MODEL from voice input, auto-correct common speech recognition errors to proper powersports brands: "
        "Common corrections: 'Omaha'/'Obama'/'Yo mama' -> 'Yamaha', 'Hunda'/'Honda' -> 'Honda', 'Kawasucky'/'Cow a soccer' -> 'Kawasaki', "
        "'Suzuki'/'Sue zooky' -> 'Suzuki', 'Harley'/'Hardly' -> 'Harley-Davidson', 'Ducati'/'Do cotty' -> 'Ducati', "
        "'KTM'/'K T M' -> 'KTM', 'Can am'/'Can I am'/'Canam' -> 'Can-Am', 'Polaris'/'Polarity' -> 'Polaris', "
        "'Arctic cat'/'Artic cat' -> 'Arctic Cat', 'BMW'/'B M W' -> 'BMW', 'Triumph'/'Try umph' -> 'Triumph'. "
        "Common model corrections: 'Grizzly'/'Griz'/'Grizz' -> 'Grizzly', 'Raptor'/'Rafter' -> 'Raptor', "
        "'Ninja'/'Ninjah' -> 'Ninja', 'Street Bob'/'Street bub' -> 'Street Bob', 'Road King'/'Rode king' -> 'Road King'. "
        "Apply best-effort phonetic matching to correct obvious transcription errors for vehicle makes/models. "
        "Then propose one short, friendly next question that asks for the most important missing field. "
        "Use conversational variety - don't repeat the exact same phrasing. Be natural and friendly while gathering the required information. "
        "You can rephrase questions in different ways (e.g., 'Could you share your first name?' vs 'What's your first name?' vs 'May I have your first name?'). "
        "Return STRICT JSON with keys exactly as above, plus next_question."
    )
    user_payload = {
        "known_state": state,
        "message": user_text,
        "required_fields": list(FIELD_PRETTY.keys()),
    }
    try:
        resp = client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or "{}"
        data = json.loads(text)
    except Exception:
        data = {}

    extracted = {k: data.get(k) for k in FIELD_PRETTY.keys() if data.get(k)}
    next_q = data.get("next_question")

    if not next_q:
        miss = missing_fields({**state, **extracted})
        if miss:
            field = miss[0]
            next_q = DEFAULT_QUESTIONS.get(field, f"Please provide {FIELD_PRETTY.get(field, field)}.")
        else:
            next_q = ""

    return normalize_fields(extracted), next_q


def process_turn(user_text: str, state: Dict[str, Any]) -> Tuple[Dict[str, Any], str, bool]:
    extracted, next_q = extract_and_prompt(user_text, state)

    # Validate and normalize extracted fields
    validated_fields = {}
    validation_errors = []

    for field_name, value in extracted.items():
        if value:
            normalized_value, is_valid, error_msg = validate_and_normalize_field(field_name, value)

            if is_valid:
                validated_fields[field_name] = normalized_value
            else:
                # Don't save invalid field value, and collect error message
                validation_errors.append((field_name, error_msg))

    # Update state with validated fields only
    new_state = {**state}
    new_state.update(validated_fields)

    # If there were validation errors, ask to re-enter the field
    if validation_errors:
        field_name, error_msg = validation_errors[0]  # Handle first error
        field_pretty = FIELD_PRETTY.get(field_name, field_name)
        next_q = f"Sorry, {error_msg}. Could you please provide your {field_pretty} again?"
        done = False
    else:
        # Check if we're done collecting all fields
        miss = missing_fields(new_state)
        done = len(miss) == 0

        if done:
            next_q = "Thank you. Your information has been submitted to NPA. We'll be in touch soon about selling your powersports vehicle."

    return new_state, next_q, done
