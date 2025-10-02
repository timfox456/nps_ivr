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
        new_state, next_q, done = process_turn(body, session.state or {})
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
        resp = VoiceResponse()
        gather = Gather(input="speech dtmf", action="/twilio/voice/collect", method="POST", timeout=6, speechTimeout="auto")
        gather.say("Welcome to National Powersports Auctions. Tell me what you're selling and your contact info. For example, I am selling a 2018 Harley Davidson Sportster. My name is Jane Doe, phone 555 123 4567, email jane at example dot com.")
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
        new_state, next_q, done = process_turn(speech_result, session.state or {})
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
