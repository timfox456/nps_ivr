import json
import re
from typing import Dict, Any, Tuple
from openai import OpenAI
from .config import settings
from .models import missing_fields, FIELD_PRETTY

_client: OpenAI | None = None

def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client

DEFAULT_QUESTIONS = {
    "first_name": "What is your first name?",
    "last_name": "What is your last name?",
    "address": "What is your full mailing address?",
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
        "You are a lead intake assistant for National Powersports Auctions (NPA). "
        "From the user's message, extract any of these fields if present: first_name, last_name, address, phone, email, vehicle_make, vehicle_model, vehicle_year. "
        "Then propose one short, friendly next question that asks for the most important missing field. "
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
            temperature=0.2,
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
    new_state = {**state}
    new_state.update(extracted)
    miss = missing_fields(new_state)
    done = len(miss) == 0

    if done:
        next_q = "Thanks! We have everything we need."

    return new_state, next_q, done
