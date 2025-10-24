import json
import logging
from fastapi import FastAPI, Request, Form, WebSocket
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather, Connect, Stream
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from .config import settings
from .db import SessionLocal, init_db
from .models import ConversationSession, missing_fields
from .llm import process_turn
from .salesforce import create_lead
from .validation import normalize_phone, validate_phone
from .voice_openai import TwilioMediaStreamHandler
from .voice_openai_optimized import OptimizedRealtimeHandler

logger = logging.getLogger(__name__)

app = FastAPI(title="NPA IVR & SMS Intake")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

# Utilities

# NATO Phonetic Alphabet for clear email spelling
NATO_ALPHABET = {
    'a': 'Alpha', 'b': 'Bravo', 'c': 'Charlie', 'd': 'Delta', 'e': 'Echo',
    'f': 'Foxtrot', 'g': 'Golf', 'h': 'Hotel', 'i': 'India', 'j': 'Juliet',
    'k': 'Kilo', 'l': 'Lima', 'm': 'Mike', 'n': 'November', 'o': 'Oscar',
    'p': 'Papa', 'q': 'Quebec', 'r': 'Romeo', 's': 'Sierra', 't': 'Tango',
    'u': 'Uniform', 'v': 'Victor', 'w': 'Whiskey', 'x': 'X-ray', 'y': 'Yankee',
    'z': 'Zulu',
    '0': 'Zero', '1': 'One', '2': 'Two', '3': 'Three', '4': 'Four',
    '5': 'Five', '6': 'Six', '7': 'Seven', '8': 'Eight', '9': 'Nine'
}

def format_email_for_speech(email: str) -> tuple[str, str]:
    """
    Format an email address for clear speech synthesis.

    Returns tuple of (normal_speech, spelled_speech):
    - normal_speech: "tfox at yahoo dot com"
    - spelled_speech: "that's T as in Tango, F as in Foxtrot, O as in Oscar, X as in X-ray at yahoo dot com"

    Example usage:
        normal, spelled = format_email_for_speech("tfox@yahoo.com")
        # normal = "tfox at yahoo dot com"
        # spelled = "that's T as in Tango, F as in Foxtrot, O as in Oscar, X as in X-ray at yahoo dot com"
    """
    if '@' not in email:
        return email, email

    local, domain = email.split('@', 1)

    # Normal speech: just replace @ and dots
    domain_spoken = domain.replace('.', ' dot ')
    normal_speech = f"{local} at {domain_spoken}"

    # Spelled speech: NATO alphabet for local part
    local_parts = []
    for char in local.lower():
        if char in NATO_ALPHABET:
            local_parts.append(f"{char.upper()} as in {NATO_ALPHABET[char]}")
        elif char == '.':
            local_parts.append("dot")
        elif char == '_':
            local_parts.append("underscore")
        elif char == '-':
            local_parts.append("dash")
        else:
            local_parts.append(char)

    # Join with commas for pauses
    local_spelled = ", ".join(local_parts)
    spelled_speech = f"that's {local_spelled} at {domain_spoken}"

    return normal_speech, spelled_speech

def extract_caller_phone(from_number: str | None) -> tuple[str | None, str | None]:
    """
    Extract and normalize caller ID phone number.

    Returns:
        Tuple of (normalized_phone, formatted_for_speech)
        - normalized_phone: Standardized format like "(555) 223-4567" or None if invalid
        - formatted_for_speech: Friendly format for TTS like "555-223-4567" or None if invalid
    """
    if not from_number or from_number == "unknown":
        return None, None

    # Validate and normalize the phone number
    is_valid, _ = validate_phone(from_number)
    if not is_valid:
        return None, None

    normalized = normalize_phone(from_number)

    # Extract digits for speech-friendly format
    import re
    digits = re.sub(r'\D', '', normalized)
    if len(digits) == 10:
        # Format as "555-223-4567" for better TTS pronunciation
        formatted_speech = f"{digits[0:3]}-{digits[3:6]}-{digits[6:10]}"
        return normalized, formatted_speech

    return normalized, normalized


def get_or_create_session(db: Session, channel: str, session_key: str, from_number: str | None, to_number: str | None) -> ConversationSession:
    obj = (
        db.query(ConversationSession)
        .filter(ConversationSession.channel == channel, ConversationSession.session_key == session_key)
        .first()
    )
    if obj:
        return obj
    obj = ConversationSession(channel=channel, session_key=session_key, from_number=from_number, to_number=to_number, state={})
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

REQUIRED_FIELDS = [
    "full_name",
    "address",
    "phone",
    "email",
    "vehicle_make",
    "vehicle_model",
    "vehicle_year",
]

# Twilio SMS
@app.post("/twilio/sms", response_class=PlainTextResponse)
async def twilio_sms(request: Request):
    form = dict(await request.form())
    from_number = form.get("From") or "unknown"
    to_number = form.get("To") or "unknown"
    body = form.get("Body", "").strip()
    # Use from_number as session key so all messages from same number are in same conversation
    session_key = from_number

    db = SessionLocal()
    try:
        session = get_or_create_session(db, "sms", session_key, from_number, to_number)

        # Check for reset keywords
        reset_keywords = ["hi", "hello", "restart", "reset", "start over", "start again", "begin"]
        if any(keyword in body.lower() for keyword in reset_keywords):
            # Reset the session state
            session.state = {}
            session.last_prompt_field = "full_name"
            session.last_prompt = "What's your full name?"
            session.status = "open"
            flag_modified(session, "state")
            db.commit()

            # Send welcome message
            resp = MessagingResponse()
            resp.message("Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle. What's your full name?")
            return PlainTextResponse(str(resp), media_type="application/xml")

        # Pre-populate phone number from caller ID if not already set
        current_state = session.state or {}

        # Check if this is the first message - use last_prompt_field as indicator
        # If last_prompt_field is not set, this is the first user message
        is_first_message = not session.last_prompt_field

        if not current_state.get("phone"):
            caller_phone, _ = extract_caller_phone(from_number)
            if caller_phone:
                current_state["phone"] = caller_phone

        # Send welcome message for first interaction
        if is_first_message:
            resp = MessagingResponse()
            resp.message("Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle. What's your full name?")
            session.state = current_state
            session.last_prompt_field = "full_name"
            session.last_prompt = "What's your full name?"
            flag_modified(session, "state")
            db.commit()
            return PlainTextResponse(str(resp), media_type="application/xml")

        # Pass last_prompt_field for better context tracking
        last_asked = session.last_prompt_field if session.last_prompt_field else None
        new_state, next_q, done = process_turn(body, current_state, last_asked)

        # Determine which field we're asking about next for better context tracking
        if not done:
            miss = missing_fields(new_state)
            if miss:
                session.last_prompt_field = miss[0]
                session.last_prompt = next_q

        session.state = new_state
        flag_modified(session, "state")
        # Send lead when done
        if done and session.status != "closed":
            # Add channel info for lead creation
            new_state["_channel"] = "sms"
            await create_lead(new_state)
            session.status = "closed"
        db.commit()

        resp = MessagingResponse()
        resp.message(next_q)
        return PlainTextResponse(str(resp), media_type="application/xml")
    finally:
        db.close()

# Twilio Voice (Legacy IVR with Twilio TTS) - keeping as backup
@app.post("/twilio/voice-ivr", response_class=PlainTextResponse)
async def twilio_voice_ivr(request: Request):
    form = dict(await request.form())
    call_sid = form.get("CallSid") or "call"
    from_number = form.get("From") or "unknown"
    to_number = form.get("To") or "unknown"

    db = SessionLocal()
    try:
        session = get_or_create_session(db, "voice", call_sid, from_number, to_number)

        # Check if we can extract caller ID
        caller_phone, phone_speech = extract_caller_phone(from_number)

        resp = VoiceResponse()
        gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")

        if caller_phone and phone_speech:
            # Store the detected phone in a temporary field for confirmation
            current_state = session.state or {}
            current_state["_pending_phone"] = caller_phone
            session.state = current_state
            flag_modified(session, "state")
            db.commit()

            # Ask for confirmation
            gather.say(f"Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle. I see you're calling from {phone_speech}. Is this the best number to reach you? Please say yes or no.")
        else:
            # No caller ID available, proceed normally
            gather.say("Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle. What's your full name?")

        resp.append(gather)
        resp.redirect("/twilio/voice-ivr/collect")
        return PlainTextResponse(str(resp), media_type="application/xml")
    finally:
        db.close()

# Voice gather handler (Legacy IVR)
@app.post("/twilio/voice-ivr/collect", response_class=PlainTextResponse)
async def twilio_voice_ivr_collect(request: Request):
    form = dict(await request.form())
    call_sid = form.get("CallSid") or "call"
    speech_result = form.get("SpeechResult") or form.get("Digits") or ""

    db = SessionLocal()
    try:
        session = get_or_create_session(db, "voice", call_sid, form.get("From"), form.get("To"))

        # Check for reset keywords
        reset_keywords = ["restart", "reset", "start over", "start again", "begin again"]
        if any(keyword in speech_result.lower() for keyword in reset_keywords):
            # Reset the session state
            session.state = {}
            session.last_prompt_field = "full_name"
            session.last_prompt = "What's your full name?"
            session.status = "open"
            flag_modified(session, "state")
            db.commit()

            # Send welcome message and ask for name
            resp = VoiceResponse()
            gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
            gather.say("Restarting. Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle. What's your full name?")
            resp.append(gather)
            resp.redirect("/twilio/voice-ivr/collect")
            return PlainTextResponse(str(resp), media_type="application/xml")

        current_state = session.state or {}

        # Clean up phone confirmation flag if phone is already saved
        # This prevents re-entering confirmation logic after it's complete
        if "_phone_confirmed" in current_state and "phone" in current_state and "_pending_phone" not in current_state:
            del current_state["_phone_confirmed"]
            session.state = current_state
            flag_modified(session, "state")
            db.commit()

        # Check if we're waiting for phone number confirmation from caller ID
        # Only process this if we have a pending phone and haven't confirmed yet
        if "_pending_phone" in current_state and "_phone_confirmed" not in current_state:
            # User is responding to phone confirmation question
            response_lower = speech_result.lower().strip()

            # Check for affirmative responses
            if any(word in response_lower for word in ["yes", "yeah", "yep", "correct", "right", "sure", "okay", "ok", "yup"]):
                # User confirmed, save the phone number
                current_state["phone"] = current_state["_pending_phone"]
                del current_state["_pending_phone"]
                current_state["_phone_confirmed"] = True  # Mark as confirmed to prevent re-entry
                session.state = current_state
                flag_modified(session, "state")
                db.commit()

                # Continue with normal flow - ask for full name
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("Great! Now, what's your full name?")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            # Check for negative responses
            elif any(word in response_lower for word in ["no", "nope", "nah", "different", "another", "change"]):
                # User wants different number
                del current_state["_pending_phone"]
                current_state["_phone_confirmed"] = True  # Mark as handled to prevent re-entry
                session.state = current_state
                flag_modified(session, "state")
                db.commit()

                # Ask them to provide their phone number
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("No problem. What phone number would you like us to use?")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            else:
                # Unclear response, ask again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("I didn't catch that. Is this the best number to reach you? Please say yes or no.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

        # Check if we're waiting for phone number confirmation (from user-provided phone)
        if "_pending_phone_confirm" in current_state:
            response_lower = speech_result.lower().strip()

            # Check for affirmative responses
            if any(word in response_lower for word in ["yes", "yeah", "yep", "correct", "right", "sure", "okay", "ok", "yup"]):
                # User confirmed, save the phone number
                current_state["phone"] = current_state["_pending_phone_confirm"]
                del current_state["_pending_phone_confirm"]
                if "_pending_phone_confirm_speech" in current_state:
                    del current_state["_pending_phone_confirm_speech"]
                session.state = current_state
                flag_modified(session, "state")
                db.commit()
                db.refresh(session)

                # Continue with next question
                miss = missing_fields(current_state)
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                if miss:
                    from .llm import DEFAULT_QUESTIONS
                    from .models import FIELD_PRETTY
                    next_field = miss[0]
                    next_q = DEFAULT_QUESTIONS.get(next_field, f"What is your {FIELD_PRETTY.get(next_field, next_field)}?")
                    gather.say(f"Got it. {next_q}")
                else:
                    gather.say("Great! Let me get the rest of your information.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            # Check for negative responses
            elif any(word in response_lower for word in ["no", "nope", "nah", "different", "incorrect", "wrong"]):
                # User says number is wrong
                del current_state["_pending_phone_confirm"]
                if "_pending_phone_confirm_speech" in current_state:
                    del current_state["_pending_phone_confirm_speech"]
                session.state = current_state
                flag_modified(session, "state")
                db.commit()
                db.refresh(session)

                # Ask them to provide their phone number again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("Sorry about that. Please tell me your phone number again.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            else:
                # Unclear response, ask again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                phone_speech = current_state.get("_pending_phone_confirm_speech", "")
                gather.say(f"I didn't catch that. I heard your phone number is {phone_speech}. Is that correct? Please say yes or no.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

        # Check if we're waiting for vehicle information confirmation
        if "_pending_vehicle_confirm" in current_state:
            response_lower = speech_result.lower().strip()

            # Check for affirmative responses
            if any(word in response_lower for word in ["yes", "yeah", "yep", "correct", "right", "sure", "okay", "ok", "yup"]):
                # User confirmed, save the vehicle info
                if "_pending_vehicle_make" in current_state:
                    current_state["vehicle_make"] = current_state["_pending_vehicle_make"]
                    del current_state["_pending_vehicle_make"]
                if "_pending_vehicle_model" in current_state:
                    current_state["vehicle_model"] = current_state["_pending_vehicle_model"]
                    del current_state["_pending_vehicle_model"]
                if "_pending_vehicle_year" in current_state:
                    current_state["vehicle_year"] = current_state["_pending_vehicle_year"]
                    del current_state["_pending_vehicle_year"]
                del current_state["_pending_vehicle_confirm"]
                if "_pending_vehicle_speech" in current_state:
                    del current_state["_pending_vehicle_speech"]
                session.state = current_state
                flag_modified(session, "state")
                db.commit()
                db.refresh(session)

                # Continue with next question
                miss = missing_fields(current_state)
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                if miss:
                    from .llm import DEFAULT_QUESTIONS
                    from .models import FIELD_PRETTY
                    next_field = miss[0]
                    next_q = DEFAULT_QUESTIONS.get(next_field, f"What is your {FIELD_PRETTY.get(next_field, next_field)}?")
                    gather.say(f"Great! {next_q}")
                else:
                    gather.say("Great! We have everything we need.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            # Check for negative responses
            elif any(word in response_lower for word in ["no", "nope", "nah", "different", "incorrect", "wrong"]):
                # User says vehicle info is wrong - ask again for the specific fields
                if "_pending_vehicle_make" in current_state:
                    del current_state["_pending_vehicle_make"]
                if "_pending_vehicle_model" in current_state:
                    del current_state["_pending_vehicle_model"]
                if "_pending_vehicle_year" in current_state:
                    del current_state["_pending_vehicle_year"]
                del current_state["_pending_vehicle_confirm"]
                if "_pending_vehicle_speech" in current_state:
                    del current_state["_pending_vehicle_speech"]
                session.state = current_state
                flag_modified(session, "state")
                db.commit()
                db.refresh(session)

                # Ask for the vehicle information again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")

                # Determine which field to re-ask
                miss = missing_fields(current_state)
                if "vehicle_make" in miss or "vehicle_model" in miss or "vehicle_year" in miss:
                    gather.say("No problem. Let's try again. What is the make, model, and year of your vehicle?")
                else:
                    gather.say("Sorry about that. Please tell me the vehicle information again.")

                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            else:
                # Unclear response, ask again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                vehicle_speech = current_state.get("_pending_vehicle_speech", "")
                gather.say(f"I didn't catch that. I heard {vehicle_speech}. Is that correct? Please say yes or no.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

        # Check if we're waiting for email confirmation
        if "_pending_email" in current_state:
            response_lower = speech_result.lower().strip()

            # Check for affirmative responses
            if any(word in response_lower for word in ["yes", "yeah", "yep", "correct", "right", "sure", "okay", "ok", "yup"]):
                # User confirmed, save the email
                current_state["email"] = current_state["_pending_email"]
                del current_state["_pending_email"]
                if "_pending_email_normal" in current_state:
                    del current_state["_pending_email_normal"]
                if "_pending_email_spelled" in current_state:
                    del current_state["_pending_email_spelled"]
                session.state = current_state
                flag_modified(session, "state")
                db.commit()
                db.refresh(session)

                # Continue with next question
                miss = missing_fields(current_state)
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                if miss:
                    from .llm import DEFAULT_QUESTIONS
                    from .models import FIELD_PRETTY
                    next_field = miss[0]
                    next_q = DEFAULT_QUESTIONS.get(next_field, f"What is your {FIELD_PRETTY.get(next_field, next_field)}?")
                    gather.say(f"Perfect. {next_q}")
                else:
                    gather.say("Perfect! We have everything we need.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            # Check for negative responses
            elif any(word in response_lower for word in ["no", "nope", "nah", "different", "incorrect", "wrong"]):
                # User says email is wrong
                del current_state["_pending_email"]
                if "_pending_email_normal" in current_state:
                    del current_state["_pending_email_normal"]
                if "_pending_email_spelled" in current_state:
                    del current_state["_pending_email_spelled"]
                session.state = current_state
                flag_modified(session, "state")
                db.commit()
                db.refresh(session)

                # Ask them to provide their email again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("Sorry about that. Please tell me your email address again, saying 'at' for the at symbol and 'dot' for periods.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

            else:
                # Unclear response, ask again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                email_normal = current_state.get("_pending_email_normal", "")
                email_spelled = current_state.get("_pending_email_spelled", "")

                gather.say(f"I didn't catch that. Let me repeat: {email_normal}.")
                gather.pause(length=1)
                gather.say(email_spelled, rate="slow")
                gather.pause(length=1)
                gather.say("Is that correct? Please say yes or no.")
                resp.append(gather)
                resp.redirect("/twilio/voice-ivr/collect")
                return PlainTextResponse(str(resp), media_type="application/xml")

        # Normal processing flow
        new_state, next_q, done = process_turn(speech_result, current_state)

        # Check if we just collected a phone number or email that needs confirmation
        # Skip if we already have a pending confirmation or if phone was already confirmed
        if ("phone" in new_state and "phone" not in current_state and
            "_pending_phone" not in current_state and
            "_pending_phone_confirm" not in current_state and
            "_pending_phone_confirm_speech" not in current_state):
            # A new phone number was just extracted - need confirmation
            import re
            phone = new_state["phone"]
            digits = re.sub(r'\D', '', phone)
            if len(digits) == 10:
                # Format for speech: "555-223-4567"
                phone_speech = f"{digits[0:3]}, {digits[3:6]}, {digits[6:10]}"

                # Store the phone for confirmation
                new_state["_pending_phone_confirm"] = phone
                new_state["_pending_phone_confirm_speech"] = phone_speech
                del new_state["phone"]  # Don't save yet
                session.state = new_state
                flag_modified(session, "state")
                db.commit()

                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say(f"I heard your phone number is {phone_speech}. Is that correct?")
                resp.append(gather)
                return PlainTextResponse(str(resp), media_type="application/xml")

        if "email" in new_state and "email" not in current_state:
            # A new email was just extracted - need confirmation
            email = new_state["email"]

            # Format email: normal first, then spelled with NATO alphabet
            email_normal, email_spelled = format_email_for_speech(email)

            # Store the email for confirmation
            new_state["_pending_email"] = email
            new_state["_pending_email_normal"] = email_normal
            new_state["_pending_email_spelled"] = email_spelled
            del new_state["email"]  # Don't save yet
            session.state = new_state
            flag_modified(session, "state")
            db.commit()

            resp = VoiceResponse()
            gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
            # Say it normally first, then spell it out
            gather.say(f"I heard your email is {email_normal}.")
            gather.pause(length=1)
            gather.say(email_spelled, rate="slow")
            gather.pause(length=1)
            gather.say("Is that correct? Please say yes or no.")
            resp.append(gather)
            return PlainTextResponse(str(resp), media_type="application/xml")

        # Check if we just collected vehicle information that should be confirmed
        # We'll confirm if any vehicle field was newly extracted
        vehicle_fields_changed = (
            ("vehicle_make" in new_state and "vehicle_make" not in current_state) or
            ("vehicle_model" in new_state and "vehicle_model" not in current_state) or
            ("vehicle_year" in new_state and "vehicle_year" not in current_state)
        )

        if vehicle_fields_changed:
            # Build confirmation message
            vehicle_parts = []
            if "vehicle_year" in new_state:
                vehicle_parts.append(new_state["vehicle_year"])
                new_state["_pending_vehicle_year"] = new_state["vehicle_year"]
                del new_state["vehicle_year"]
            if "vehicle_make" in new_state:
                vehicle_parts.append(new_state["vehicle_make"])
                new_state["_pending_vehicle_make"] = new_state["vehicle_make"]
                del new_state["vehicle_make"]
            if "vehicle_model" in new_state:
                vehicle_parts.append(new_state["vehicle_model"])
                new_state["_pending_vehicle_model"] = new_state["vehicle_model"]
                del new_state["vehicle_model"]

            vehicle_speech = " ".join(vehicle_parts)
            new_state["_pending_vehicle_confirm"] = True
            new_state["_pending_vehicle_speech"] = vehicle_speech
            session.state = new_state
            flag_modified(session, "state")
            db.commit()

            resp = VoiceResponse()
            gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
            gather.say(f"I heard {vehicle_speech}. Is that correct?")
            resp.append(gather)
            return PlainTextResponse(str(resp), media_type="application/xml")

        session.state = new_state
        flag_modified(session, "state")
        if done and session.status != "closed":
            # Add channel info for lead creation
            new_state["_channel"] = "voice"
            await create_lead(new_state)
            session.status = "closed"
        db.commit()

        resp = VoiceResponse()
        if done:
            resp.say(next_q)
            resp.hangup()
        else:
            gather = Gather(input="speech dtmf", action="/twilio/voice-ivr/collect", method="POST", timeout=6, speechTimeout="auto")
            gather.say(next_q)
            resp.append(gather)
            resp.redirect("/twilio/voice-ivr/collect")
        return PlainTextResponse(str(resp), media_type="application/xml")
    finally:
        db.close()

# Twilio Voice with OpenAI Realtime API - Proxied mode (for testing/debugging)
@app.post("/twilio/voice-realtime-proxied", response_class=PlainTextResponse)
async def twilio_voice_realtime_proxied(request: Request):
    """
    Handle incoming voice calls using OpenAI Realtime API
    This provides natural, low-latency voice conversations
    """
    form = dict(await request.form())
    call_sid = form.get("CallSid") or "call"

    logger.info(f"Voice call received: {call_sid}")

    # Return TwiML that connects to our WebSocket endpoint
    # Use the full host from request headers (includes ngrok domain)
    host = request.headers.get('host', request.url.hostname)
    resp = VoiceResponse()

    # Add a Say as fallback in case stream fails
    resp.say("Connecting to voice assistant. Please wait.")

    connect = Connect()
    stream = Stream(url=f'wss://{host}/twilio/voice/stream')
    connect.append(stream)
    resp.append(connect)

    # Fallback if stream fails
    resp.say("Sorry, we're experiencing technical difficulties. Please try again later.")
    resp.hangup()

    logger.info(f"Returning TwiML with stream URL: wss://{host}/twilio/voice/stream")
    return PlainTextResponse(str(resp), media_type="application/xml")


@app.websocket("/twilio/voice/stream")
async def twilio_voice_stream(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams with OpenAI Realtime API
    """
    call_sid = None
    try:
        await websocket.accept()
        logger.info("WebSocket connection accepted")

        # Twilio sends messages in this order: connected, start, media, media, ...
        # We need to wait for the "start" event to get the call SID
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event_type = data.get("event")

            logger.info(f"Received event: {event_type}")

            if event_type == "connected":
                logger.info("Twilio Media Stream connected")
                continue

            elif event_type == "start":
                call_sid = data["start"]["callSid"]
                stream_sid = data["start"]["streamSid"]
                logger.info(f"Starting OpenAI Realtime stream for call {call_sid}, stream {stream_sid}")

                # Create handler and start processing
                # Pass the start data to the handler since we already consumed it
                handler = TwilioMediaStreamHandler(websocket, call_sid, stream_sid)
                await handler.start()
                break

            else:
                logger.warning(f"Unexpected event before start: {event_type}")

    except Exception as e:
        logger.error(f"WebSocket error for call {call_sid}: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass


@app.get("/health")
def health():
    return {"ok": True}

# Twilio Voice with OpenAI Realtime API - Optimized Production Mode
@app.post("/twilio/voice-realtime", response_class=PlainTextResponse)
async def twilio_voice_realtime_optimized(request: Request):
    """
    Optimized production endpoint with minimal overhead
    - Reduced logging
    - Direct audio forwarding
    - No mid-call database writes
    """
    form = dict(await request.form())
    call_sid = form.get("CallSid") or "call"

    logger.info(f"Optimized voice call: {call_sid}")

    host = request.headers.get('host', request.url.hostname)
    resp = VoiceResponse()
    resp.say("Connecting.")

    connect = Connect()
    stream = Stream(url=f'wss://{host}/twilio/voice/stream-optimized')
    connect.append(stream)
    resp.append(connect)

    return PlainTextResponse(str(resp), media_type="application/xml")


@app.websocket("/twilio/voice/stream-optimized")
async def twilio_voice_stream_optimized(websocket: WebSocket):
    """Optimized WebSocket endpoint for production"""
    call_sid = None
    try:
        await websocket.accept()

        # Wait for start event
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event_type = data.get("event")

            if event_type == "connected":
                continue
            elif event_type == "start":
                call_sid = data["start"]["callSid"]
                stream_sid = data["start"]["streamSid"]

                # Use optimized handler
                handler = OptimizedRealtimeHandler(websocket, call_sid, stream_sid)
                await handler.start()
                break

    except Exception as e:
        logger.error(f"Optimized WS error {call_sid}: {e}")
        try:
            await websocket.close()
        except:
            pass


# Twilio Voice - Default endpoint (switchable)
@app.post("/twilio/voice", response_class=PlainTextResponse)
async def twilio_voice(request: Request):
    """
    Default voice endpoint - currently uses proxied mode for testing

    Change to optimized for production:
    return await twilio_voice_realtime_optimized(request)
    """
    # For now, use proxied mode with full logging
    return await twilio_voice_realtime_proxied(request)


@app.get("/test/voice-twiml")
async def test_voice_twiml(request: Request):
    """Test endpoint to see what TwiML is generated"""
    host = request.headers.get('host', request.url.hostname)
    resp = VoiceResponse()
    connect = Connect()
    stream = Stream(url=f'wss://{host}/twilio/voice/stream')
    connect.append(stream)
    resp.append(connect)
    return PlainTextResponse(str(resp), media_type="application/xml")
