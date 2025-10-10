from fastapi import FastAPI, Request, Form
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from twilio.twiml.messaging_response import MessagingResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from sqlalchemy.orm import Session
from .config import settings
from .db import SessionLocal, init_db
from .models import ConversationSession, missing_fields
from .llm import process_turn
from .salesforce import create_lead
from .validation import normalize_phone, validate_phone

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
    "first_name",
    "last_name",
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
    sms_sid = form.get("SmsSid") or form.get("MessageSid") or from_number or "sms"

    db = SessionLocal()
    try:
        session = get_or_create_session(db, "sms", sms_sid, from_number, to_number)

        # Pre-populate phone number from caller ID if not already set
        current_state = session.state or {}
        if not current_state.get("phone"):
            caller_phone, _ = extract_caller_phone(from_number)
            if caller_phone:
                current_state["phone"] = caller_phone

        new_state, next_q, done = process_turn(body, current_state)
        session.state = new_state
        # Send lead when done
        if done and session.status != "closed":
            await create_lead(new_state)
            session.status = "closed"
        db.commit()

        resp = MessagingResponse()
        if done:
            resp.message("Thank you! Your info has been submitted to NPA.")
        else:
            resp.message(next_q)
        return PlainTextResponse(str(resp), media_type="application/xml")
    finally:
        db.close()

# Twilio Voice: initial call
@app.post("/twilio/voice", response_class=PlainTextResponse)
async def twilio_voice(request: Request):
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
        gather = Gather(input="speech dtmf", action="/twilio/voice/collect", method="POST", timeout=6, speechTimeout="auto")

        if caller_phone and phone_speech:
            # Store the detected phone in a temporary field for confirmation
            current_state = session.state or {}
            current_state["_pending_phone"] = caller_phone
            session.state = current_state
            db.commit()

            # Ask for confirmation
            gather.say(f"Hi! Welcome to National Powersports Auctions. I see you're calling from {phone_speech}. Is this the best number to reach you? Please say yes or no.")
        else:
            # No caller ID available, proceed normally
            gather.say("Hi! Welcome to National Powersports Auctions. I'll help you get started. What's your first name?")

        resp.append(gather)
        resp.redirect("/twilio/voice/collect")
        return PlainTextResponse(str(resp), media_type="application/xml")
    finally:
        db.close()

# Voice gather handler
@app.post("/twilio/voice/collect", response_class=PlainTextResponse)
async def twilio_voice_collect(request: Request):
    form = dict(await request.form())
    call_sid = form.get("CallSid") or "call"
    speech_result = form.get("SpeechResult") or form.get("Digits") or ""

    db = SessionLocal()
    try:
        session = get_or_create_session(db, "voice", call_sid, form.get("From"), form.get("To"))
        current_state = session.state or {}

        # Check if we're waiting for phone number confirmation
        if "_pending_phone" in current_state and "phone" not in current_state:
            # User is responding to phone confirmation question
            response_lower = speech_result.lower().strip()

            # Check for affirmative responses
            if any(word in response_lower for word in ["yes", "yeah", "yep", "correct", "right", "sure", "okay", "ok", "yup"]):
                # User confirmed, save the phone number
                current_state["phone"] = current_state["_pending_phone"]
                del current_state["_pending_phone"]
                session.state = current_state
                db.commit()

                # Continue with normal flow - ask for first name
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("Great! Now, what's your first name?")
                resp.append(gather)
                return PlainTextResponse(str(resp), media_type="application/xml")

            # Check for negative responses
            elif any(word in response_lower for word in ["no", "nope", "nah", "different", "another", "change"]):
                # User wants different number
                del current_state["_pending_phone"]
                session.state = current_state
                db.commit()

                # Ask them to provide their phone number
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("No problem. What phone number would you like us to use?")
                resp.append(gather)
                return PlainTextResponse(str(resp), media_type="application/xml")

            else:
                # Unclear response, ask again
                resp = VoiceResponse()
                gather = Gather(input="speech dtmf", action="/twilio/voice/collect", method="POST", timeout=6, speechTimeout="auto")
                gather.say("I didn't catch that. Is this the best number to reach you? Please say yes or no.")
                resp.append(gather)
                return PlainTextResponse(str(resp), media_type="application/xml")

        # Normal processing flow
        new_state, next_q, done = process_turn(speech_result, current_state)
        session.state = new_state
        if done and session.status != "closed":
            await create_lead(new_state)
            session.status = "closed"
        db.commit()

        resp = VoiceResponse()
        if done:
            resp.say("Thank you. Your information has been submitted to N P A. Goodbye.")
            resp.hangup()
        else:
            gather = Gather(input="speech dtmf", action="/twilio/voice/collect", method="POST", timeout=6, speechTimeout="auto")
            gather.say(next_q)
            resp.append(gather)
        return PlainTextResponse(str(resp), media_type="application/xml")
    finally:
        db.close()

@app.get("/health")
def health():
    return {"ok": True}
