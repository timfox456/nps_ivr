import json
import re
import time
import logging
from typing import Dict, Any, Tuple
from openai import OpenAI
from .config import settings
from .models import missing_fields, FIELD_PRETTY
from .validation import validate_and_normalize_field, normalize_transcribed_email
from .validation_rules import validate_zip_code, validate_vehicle_eligibility, categorize_vehicle_type, validate_make_model_match

logger = logging.getLogger(__name__)

_client: OpenAI | None = None

def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client

DEFAULT_QUESTIONS = {
    "full_name": "What is your full name?",
    "zip_code": "What is your ZIP code?",
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


def extract_and_prompt(user_text: str, state: Dict[str, Any], last_asked_field: str = None) -> Tuple[Dict[str, Any], str]:
    # Build context-aware system prompt
    context_hint = ""
    if last_asked_field:
        context_hint = f"CRITICAL CONTEXT: The user was just asked for their '{last_asked_field}'. If they provide a simple answer (like a single name or word), extract it as '{last_asked_field}'. "

    sys = (
        "You are a lead intake assistant for PowerSportBuyers.com, helping customers sell their powersports vehicles. "
        "From the user's message, extract any of these fields if present: full_name, zip_code, phone, email, vehicle_make, vehicle_model, vehicle_year. "
        "IMPORTANT: Collect fields in this EXACT order: 1) full_name, 2) zip_code, 3) phone, 4) email, 5) vehicle info (year/make/model together). "
        "Ask for the NEXT missing field in this order - do not skip ahead or go backwards unless the user volunteers information. "
        f"{context_hint}"
        "CRITICAL: For 'full_name', you should extract the complete name (first and last). "
        "If the user provides TWO or more words (like 'Tim Fox', 'John Smith', 'Sarah Johnson'), accept it as a complete full_name. "
        "ONLY if they provide a SINGLE word (like just 'John' or 'Smith'), ask for clarification: 'Thanks John! And what is your last name?' "
        "Examples: "
        "- 'Tim Fox' → Extract as full_name: 'Tim Fox' (COMPLETE - do not ask for last name) "
        "- 'John Smith' → Extract as full_name: 'John Smith' (COMPLETE) "
        "- 'John' → Do not extract yet, ask 'Thanks John! And what is your last name?' "
        "- 'Smith' → Do not extract yet, ask for first name. "
        "CRITICAL: For the 'zip_code' field, extract EXACTLY 5 digits. ZIP code MUST be 5 digits. "
        "If the user provides 4 or fewer digits, do NOT extract it - ask them to provide all 5 digits. "
        "If the user provides ZIP+4 format (12345-6789 or 123456789), extract ONLY the first 5 digits and ignore the rest. "
        "Examples: '30093' → zip_code: '30093' (VALID), '7265' → Do NOT extract, ask for 5-digit ZIP, '30093-1234' → zip_code: '30093' (extract first 5 only). "
        "IMPORTANT: When the user provides a short direct answer, use the conversation context to infer which field they're answering. "
        "Look at the known_state to see what fields are still missing. "
        "IMPORTANT: For EMAIL addresses from voice input, common transcription patterns: "
        "'at' means '@', 'dot' means '.', 'underscore' means '_', 'dash' or 'hyphen' means '-'. "
        "Examples: 'tfox at yahoo dot com' = 'tfox@yahoo.com', 'john dot smith at gmail dot com' = 'john.smith@gmail.com'. "
        "CRITICAL: Users may spell their email using phonetic alphabet (NATO, historical, or informal). Extract ONLY the letters/numbers, ignore the phonetic words. "
        "Examples: 'T as in Tango F as in Fox at yahoo dot com' = 'tf@yahoo.com', "
        "'N as in Nancy A as in Apple M as in Mary E at gmail dot com' = 'name@gmail.com', "
        "'J for John O for Oscar N for November at test dot com' = 'jon@test.com', "
        "'A as in Able B as in Baker C as in Charlie at test dot com' = 'abc@test.com'. "
        "Look for patterns like 'X as in Y', 'X for Y', 'X like Y' and extract only the first letter (X). "
        "Recognize both modern NATO (Alpha, Bravo, Charlie) and historical variants (Able, Baker, Charlie, Dog, Easy, Fox, George, How, Item, Jig, King, Love, Mike, Nan, Oboe, Peter, Queen, Roger, Sugar, Tare, Uncle, Victor, William, X-ray, Yoke, Zebra). "
        "Extract the email exactly as transcribed - validation will be handled separately. "
        "IMPORTANT: For PHONE numbers, extract all digits. Accept formats like (555) 123-4567, 555-123-4567, or 5551234567. "
        "IMPORTANT: For VEHICLE information, when user provides both make and model together (like 'Dodge Ram', '2020 Yamaha Grizzly', 'Honda CBR600'), extract BOTH fields: "
        "Examples: 'Dodge Ram' -> vehicle_make: 'Dodge', vehicle_model: 'Ram' | '2020 Yamaha Grizzly' -> vehicle_year: '2020', vehicle_make: 'Yamaha', vehicle_model: 'Grizzly' | "
        "'Honda CBR600' -> vehicle_make: 'Honda', vehicle_model: 'CBR600'. "
        "IMPORTANT: For VEHICLE MAKE/MODEL from voice input, auto-correct common speech recognition errors to proper powersports brands: "
        "Common corrections: 'Omaha'/'Obama'/'Yo mama' -> 'Yamaha', 'Hunda'/'Honda' -> 'Honda', 'Kawasucky'/'Cow a soccer' -> 'Kawasaki', "
        "'Suzuki'/'Sue zooky' -> 'Suzuki', 'Harley'/'Hardly' -> 'Harley-Davidson', 'Ducati'/'Do cotty' -> 'Ducati', "
        "'KTM'/'K T M' -> 'KTM', 'Can am'/'Can I am'/'Canam' -> 'Can-Am', 'Polaris'/'Polarity' -> 'Polaris', "
        "'Arctic cat'/'Artic cat' -> 'Arctic Cat', 'BMW'/'B M W' -> 'BMW', 'Triumph'/'Try umph' -> 'Triumph'. "
        "Common model corrections: 'Grizzly'/'Griz'/'Grizz' -> 'Grizzly', 'Raptor'/'Rafter' -> 'Raptor', "
        "'Ninja'/'Ninjah' -> 'Ninja', 'Street Bob'/'Street bub' -> 'Street Bob', 'Road King'/'Rode king' -> 'Road King'. "
        "Apply best-effort phonetic matching to correct obvious transcription errors for vehicle makes/models. "
        "Then propose one short, friendly next question that asks for the NEXT missing field in the order specified above. "
        "CRITICAL: Ask for ONLY ONE field at a time. Do not ask for multiple fields in the same message. "
        "CRITICAL: Do not repeat yourself or ask for information already provided. Check known_state carefully before asking. "
        "Use conversational variety - don't repeat the exact same phrasing. Be natural and friendly while gathering the required information. "
        "You can rephrase questions in different ways (e.g., 'Could you share your ZIP code?' vs 'What's your ZIP code?' vs 'May I have your ZIP?'). "
        "CRITICAL: Do not make assumptions. If a field is missing from known_state, you MUST ask for it explicitly. "
        "Return STRICT JSON with keys exactly as above, plus next_question."
    )
    user_payload = {
        "known_state": state,
        "message": user_text,
        "required_fields": list(FIELD_PRETTY.keys()),
    }
    try:
        start_time = time.time()
        logger.info(f"Starting OpenAI API call for SMS (model: {settings.openai_model})")

        resp = client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            temperature=0.2,  # Reduced from 0.7 for more consistent, predictable behavior
            response_format={"type": "json_object"},
        )

        api_time = time.time() - start_time
        logger.info(f"OpenAI API call completed in {api_time:.2f}s")

        text = resp.choices[0].message.content or "{}"
        data = json.loads(text)
    except Exception as e:
        api_time = time.time() - start_time
        logger.error(f"OpenAI API call failed after {api_time:.2f}s: {e}")
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


def process_turn(user_text: str, state: Dict[str, Any], last_asked_field: str = None) -> Tuple[Dict[str, Any], str, bool]:
    extracted, next_q = extract_and_prompt(user_text, state, last_asked_field)

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
            # Apply business rules validation before accepting the lead
            rejection_reason = None

            # Rule 1: Validate ZIP code (Alaska/Hawaii)
            zip_code = new_state.get("zip_code", "")
            if zip_code:
                is_valid_zip, zip_error = validate_zip_code(zip_code)
                if not is_valid_zip:
                    rejection_reason = zip_error

            # Rule 2: Validate make/model match (if ZIP is valid)
            if not rejection_reason:
                vehicle_make = new_state.get("vehicle_make", "")
                vehicle_model = new_state.get("vehicle_model", "")

                if vehicle_make and vehicle_model:
                    is_match, match_error = validate_make_model_match(vehicle_make, vehicle_model)
                    if not is_match:
                        rejection_reason = match_error

            # Rule 3: Validate vehicle eligibility (if previous rules passed)
            if not rejection_reason:
                vehicle_year = new_state.get("vehicle_year")
                vehicle_make = new_state.get("vehicle_make", "")
                vehicle_model = new_state.get("vehicle_model", "")

                if vehicle_year and vehicle_make and vehicle_model:
                    # Convert year to int
                    try:
                        year_int = int(str(vehicle_year))
                    except (ValueError, TypeError):
                        year_int = 0

                    # Infer vehicle type from make/model
                    vehicle_type = categorize_vehicle_type(vehicle_make, vehicle_model)

                    # Validate vehicle eligibility
                    is_eligible, vehicle_error = validate_vehicle_eligibility(
                        year_int, vehicle_make, vehicle_model, vehicle_type
                    )

                    if not is_eligible:
                        rejection_reason = vehicle_error

            # Set response based on validation
            if rejection_reason:
                # Lead is rejected - provide rejection message
                next_q = f"{rejection_reason} Thank you for your time."
                # Mark as done but rejected (handler will not submit to NPA)
                new_state["_rejected"] = True
                new_state["_rejection_reason"] = rejection_reason
            else:
                # Lead is accepted
                next_q = "Thank you for your information. I will start a file here and one of our agents will reach out to you in the next 24 hours to grab further information regarding your vehicle."

    return new_state, next_q, done
