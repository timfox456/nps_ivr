"""
OpenAI Realtime API integration for Twilio Voice using Media Streams

This module handles real-time voice conversations using:
- Twilio Media Streams (WebSocket) for audio streaming
- OpenAI Realtime API for natural voice conversation
- FastAPI WebSocket endpoint for handling the stream

Architecture:
    Twilio Call → /twilio/voice (TwiML with <Connect><Stream>)
    → /twilio/voice/stream (WebSocket)
    → OpenAI Realtime API (WebSocket)
"""
import asyncio
import base64
import json
import logging
from typing import Dict, Any, Optional
import websockets
from fastapi import WebSocket
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .config import settings
from .db import SessionLocal
from .models import ConversationSession, missing_fields
from .llm import process_turn
from .salesforce import create_lead
from .logging_config import get_transaction_logger, LogContext

logger = logging.getLogger(__name__)
transaction_logger = get_transaction_logger()

# OpenAI Realtime API configuration
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
OPENAI_MODEL = "gpt-realtime-mini-2025-10-06"

# System instructions for the AI assistant
SYSTEM_INSTRUCTIONS = """You are a friendly AI assistant for PowerSportBuyers.com, where we make selling your powersport vehicle stress free.

Start by saying: "Thank you for calling Power Sport Buyers dot com, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle."

Then collect the following information from the caller IN THIS ORDER:
1. Phone number (confirm from Caller ID first)
2. Full name
3. ZIP code (MUST be exactly 5 digits)
4. Vehicle information: year, make, and model (example: "2000 Yamaha Grizzly")
   - If they give you all three together (like "2000 Yamaha Grizzly"), extract year, make, and model separately
   - If they only give partial info, ask for what's missing

NOTE: Do NOT ask for email address over the phone - we will collect that later.

PHONE NUMBER RULES:
- ALWAYS start by asking about the phone number from Caller ID
- If they confirm the Caller ID number, immediately call save_lead_field to save it, then move on
- Do NOT ask for the phone number again later unless they specifically said the Caller ID was wrong
- If Caller ID phone was confirmed, it is SAVED and COMPLETE - never ask for it again

ZIP CODE COLLECTION RULES:
- Ask the user for their ZIP code
- When they provide it, repeat it back to them digit by digit to confirm
- Then call save_lead_field with the ZIP code they confirmed
- The system will automatically:
  * Extract only the digits (ignoring dashes, spaces)
  * Validate it's exactly 5 digits
  * Check if it's Alaska or Hawaii (which we don't service)
- If save_lead_field returns an error, the system will tell you what's wrong (e.g., "not enough digits" or "Alaska not serviced")
- Relay that error to the user conversationally and ask them to provide a valid ZIP code

CRITICAL CONFIRMATION RULES - ALWAYS CONFIRM THESE FIELDS:
- FULL NAME: ALWAYS confirm by repeating it back carefully: "Let me confirm, that's [First Name] [Last Name], is that correct?"
  * Listen very carefully to the name - do not make assumptions
  * If uncertain, ask them to repeat or spell it
- PHONE NUMBER from Caller ID: When confirming caller ID number, say each digit individually with brief natural pauses between groups
  * Example: "I see you're calling from 7, 2, 0... 3, 8, 1... 1, 0, 8, 4. Is this the best number to reach you?"
  * Read EACH digit separately with commas - do NOT combine digits like "ten eighty four"
  * Group the digits: first 3, then 3, then 4, with a brief pause between groups (DO NOT say the word "pause")
  * If they say "yes", immediately save it and move on - the phone is COMPLETE
- PHONE NUMBER spoken by user: ALWAYS confirm by reading back digit by digit with brief natural pauses between groups
  * Example: "Let me confirm, that's 7, 2, 0... 3, 8, 1... 1, 0, 8, 4, is that correct?"
  * Read EACH digit separately - do NOT say "ten eighty four" or combine any digits
  * DO NOT literally say the word "pause" - just use brief natural pauses between digit groups
- ZIP CODE: Confirm by reading the digits back: "Let me confirm your ZIP code, that's 9-2-5-9-2, is that correct?"
  * Don't worry about counting - the system will validate the format
  * Just repeat what you heard back to the user for confirmation
- VEHICLE INFORMATION: ALWAYS confirm year, make, and model: "Let me confirm, that's a [Year] [Make] [Model], is that correct?"
- If user repeats any information multiple times or seems frustrated, acknowledge and confirm more carefully

Be conversational and natural. Ask one question at a time.
If the caller provides multiple pieces of information at once, acknowledge what you heard and ask for the next missing field.
Be patient and helpful if they need clarification.

When you have collected a piece of information and confirmed it with the user, immediately call the save_lead_field function to save it.

IMPORTANT: When you call save_lead_field, check the response:
- If success=false, the system found a validation error (like invalid ZIP code format or Alaska/Hawaii)
- Read the error message and ask the user to provide the correct information
- Do NOT save the field if you get an error - ask the user again

SMS CONSENT - AFTER COLLECTING ALL VEHICLE INFORMATION:
- After you have saved: phone, full_name, zip_code, vehicle_year, vehicle_make, and vehicle_model
- Ask: "Are you okay if we text you with what we need to complete your offer?"
- Listen for their response (yes/no/maybe/unclear)
- Call save_lead_field with field_name="sms_consent" and field_value="yes" or "no" based on their answer
  * If they say yes/sure/okay/fine/that's fine/sounds good → use "yes"
  * If they say no/don't text me/I don't want texts → use "no"
  * If they don't respond or give an unclear answer → use "no_response"

CRITICAL - GOODBYE MESSAGE AND LEAD SUBMISSION:
- After save_lead_field for sms_consent succeeds, you MUST do these steps IN ORDER:
  1. FIRST: Say ONLY the goodbye message: "Thank you for your information. An agent will reach out to you within the next 24 hours. Have a great day, goodbye!"
  2. SECOND: Call submit_lead
- DO NOT acknowledge the consent separately (don't say "Thank you for your consent")
- DO NOT call submit_lead before saying goodbye
- DO NOT skip the goodbye message or say anything else
- Just say the complete goodbye message exactly as written, then call submit_lead
"""

# Function tools for OpenAI Realtime API
FUNCTION_TOOLS = [
    {
        "type": "function",
        "name": "save_lead_field",
        "description": "Save a single field of lead information after it has been collected and confirmed by the caller. Call this immediately after confirming each field.",
        "parameters": {
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "enum": ["full_name", "zip_code", "phone", "vehicle_year", "vehicle_make", "vehicle_model", "sms_consent"],
                    "description": "The name of the field being saved"
                },
                "field_value": {
                    "type": "string",
                    "description": "The value to save for this field"
                }
            },
            "required": ["field_name", "field_value"]
        }
    },
    {
        "type": "function",
        "name": "submit_lead",
        "description": "Submit the completed lead to the system. Call this only after ALL required fields have been collected: full_name, zip_code, phone, vehicle_year, vehicle_make, vehicle_model",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


class TwilioMediaStreamHandler:
    """Handles Twilio Media Stream WebSocket connection and OpenAI Realtime API"""

    def __init__(self, twilio_ws: WebSocket, call_sid: str, stream_sid: str = None,
                 caller_phone: str = None, phone_speech: str = None):
        self.twilio_ws = twilio_ws
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.caller_phone = caller_phone
        self.phone_speech = phone_speech
        self.openai_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session: Optional[ConversationSession] = None
        self.db: Optional[Session] = None

        # Audit logging - track transcripts for turn-by-turn logging
        self.turn_number = 0
        self.current_user_transcript = ""
        self.current_ai_transcript = ""
        self.current_turn_fields = {}

        # Track when to hang up after submit_lead
        self.should_hangup_after_next_response = False

    async def start(self):
        """Start handling the media stream"""
        try:
            print(f"=== HANDLER START: call_sid={self.call_sid} ===", flush=True)
            logger.info(f"Starting media stream handler for call {self.call_sid}")
            transaction_logger.info(f"Voice call started: {self.call_sid}")

            # Connect to OpenAI FIRST (before DB) - this is the slow operation
            print("=== CONNECTING TO OPENAI ===", flush=True)
            logger.info("Attempting to connect to OpenAI Realtime API...")
            await self._connect_to_openai()
            print("=== OPENAI CONNECTED ===", flush=True)
            logger.info("Successfully connected to OpenAI Realtime API")

            # Get or create database session (fast operation, do after OpenAI)
            print("=== CREATING DB SESSION ===", flush=True)
            self.db = SessionLocal()
            print("=== GETTING OR CREATING SESSION ===", flush=True)
            self.session = self._get_or_create_session()
            print(f"=== DB SESSION READY: {self.session.id} ===", flush=True)
            logger.info(f"Database session ready: {self.session.id}")

            # Start handling messages from both Twilio and OpenAI
            print("=== STARTING MESSAGE HANDLERS ===", flush=True)
            logger.info("Starting message handlers")

            # Use LogContext to add session metadata to all logs from here on
            with LogContext(session_id=self.session.id, twilio_call_sid=self.call_sid, channel="voice", phone=self.caller_phone or "unknown"):
                await asyncio.gather(
                    self._handle_twilio_messages(),
                    self._handle_openai_messages()
                )

        except Exception as e:
            logger.error(f"Error in media stream handler for call {self.call_sid}: {e}", exc_info=True)
            transaction_logger.error(f"Voice call error: {self.call_sid} - {str(e)}")
            raise
        finally:
            await self.cleanup()

    def _log_conversation_turn(self):
        """Log a conversation turn to the database for audit purposes"""
        from .models import ConversationTurn
        try:
            self.turn_number += 1

            turn = ConversationTurn(
                session_id=self.session.id,
                channel="voice",
                turn_number=self.turn_number,
                user_audio_transcript=self.current_user_transcript,
                ai_audio_transcript=self.current_ai_transcript,
                fields_extracted=self.current_turn_fields if self.current_turn_fields is not None else None,
                state_after_turn=dict(self.session.state) if self.session.state else None,
            )

            self.db.add(turn)
            self.db.commit()

            print(f"=== LOGGED TURN {self.turn_number}: user='{self.current_user_transcript[:50]}...', ai='{self.current_ai_transcript[:50]}...' ===", flush=True)
            logger.info(f"Logged conversation turn {self.turn_number}")

            # Reset for next turn
            self.current_user_transcript = ""
            self.current_ai_transcript = ""
            self.current_turn_fields = {}

        except Exception as e:
            logger.error(f"Error logging conversation turn: {e}", exc_info=True)

    def _get_or_create_session(self) -> ConversationSession:
        """Get or create conversation session"""
        obj = (
            self.db.query(ConversationSession)
            .filter(
                ConversationSession.channel == "voice",
                ConversationSession.session_key == self.call_sid,
                ConversationSession.status == "open"  # Only reuse open sessions
            )
            .first()
        )

        if obj:
            logger.info(f"Retrieved existing voice session {obj.id} for call {self.call_sid}")
            return obj

        # Create new session
        obj = ConversationSession(
            channel="voice",
            session_key=self.call_sid,
            from_number=None,  # Will be set from Twilio metadata
            to_number=None,
            state={},
            status="open"
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        print(f"=== CREATED NEW SESSION: {obj.id} with key={self.call_sid} ===", flush=True)
        logger.info(f"Created new voice session {obj.id} for call {self.call_sid}")
        return obj

    async def _connect_to_openai(self):
        """Connect to OpenAI Realtime API"""
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1"
        }

        self.openai_ws = await websockets.connect(
            f"{OPENAI_REALTIME_URL}?model={OPENAI_MODEL}",
            additional_headers=headers
        )

        # Build instructions with caller phone if available
        instructions = SYSTEM_INSTRUCTIONS
        if self.caller_phone and self.phone_speech:
            instructions = f"""{SYSTEM_INSTRUCTIONS}

IMPORTANT: The caller is calling from {self.phone_speech}. After your greeting, ask them: "I see you're calling from {self.phone_speech}. Is this the best number to reach you?"

If they say yes, record the phone as: {self.caller_phone} and DO NOT repeat the number back. Simply move on to the next question.
If they say no, ask them for the correct phone number."""

        # Configure the session
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": instructions,
                "voice": "alloy",  # Can be: alloy, echo, fable, onyx, nova, shimmer
                "input_audio_format": "g711_ulaw",  # Twilio uses µ-law
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",  # Server-side voice activity detection
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 1500  # Increased from 500ms to 1.5s to allow longer pauses
                },
                "tools": FUNCTION_TOOLS,
                "tool_choice": "auto"
            }
        }))

        logger.info(f"Connected to OpenAI Realtime API for call {self.call_sid}")

    async def _handle_twilio_messages(self):
        """Handle incoming messages from Twilio Media Stream"""
        try:
            print(f"=== TWILIO HANDLER STARTED: stream_sid={self.stream_sid} ===", flush=True)
            logger.info(f"Starting to handle Twilio messages for stream {self.stream_sid}")
            print("=== WAITING FOR TWILIO MESSAGES ===", flush=True)
            try:
                async for message in self.twilio_ws.iter_text():
                    print(f"=== TWILIO MESSAGE RECEIVED ===", flush=True)
                    data = json.loads(message)
                    event_type = data.get("event")

                    if event_type == "start":
                        # Extract stream info and custom parameters
                        self.stream_sid = data["start"]["streamSid"]
                        old_call_sid = self.call_sid
                        self.call_sid = data["start"]["callSid"]

                        # Update session_key to the real CallSid if it was "pending"
                        if old_call_sid == "pending" and self.session:
                            self.session.session_key = self.call_sid
                            flag_modified(self.session, "session_key")
                            self.db.commit()
                            self.db.refresh(self.session)
                            print(f"=== UPDATED SESSION KEY: pending -> {self.call_sid} ===", flush=True)
                            logger.info(f"Updated session {self.session.id} with real CallSid: {self.call_sid}")

                        # Extract custom parameters (caller_phone and phone_speech)
                        custom_params = data["start"].get("customParameters", {})
                        caller_phone = custom_params.get("caller_phone")
                        phone_speech = custom_params.get("phone_speech")

                        print(f"=== START EVENT: call_sid={self.call_sid}, caller_phone={caller_phone} ===", flush=True)
                        logger.info(f"Media stream started: {self.stream_sid}, call: {self.call_sid}")

                        # If caller phone detected, send as a system message to OpenAI
                        if caller_phone and phone_speech:
                            self.caller_phone = caller_phone
                            self.phone_speech = phone_speech

                            # Send caller ID info as a conversation item instead of updating instructions
                            caller_id_message = f"SYSTEM INFO: The caller is calling from {phone_speech} (this is a 10-digit US phone number). After your greeting, you MUST read back ALL 10 DIGITS: 'I see you're calling from {phone_speech}. Is this the best number to reach you?' CRITICAL: Count the digits - there must be exactly 10 digits when you say it. If they say yes, record the phone as {caller_phone} and do NOT repeat the number back - simply move on to the next question. If they say no, ask for the correct number and confirm it digit by digit."

                            await self.openai_ws.send(json.dumps({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "message",
                                    "role": "system",
                                    "content": [{
                                        "type": "input_text",
                                        "text": caller_id_message
                                    }]
                                }
                            }))

                            print(f"=== SENT CALLER ID TO OPENAI ===", flush=True)

                        # Always trigger an initial response to start the greeting
                        await self.openai_ws.send(json.dumps({
                            "type": "response.create"
                        }))
                        print(f"=== TRIGGERED INITIAL RESPONSE ===", flush=True)

                    elif event_type == "media":
                        # Forward audio to OpenAI
                        if self.openai_ws:
                            audio_payload = data["media"]["payload"]
                            await self.openai_ws.send(json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": audio_payload  # Already base64 encoded µ-law
                            }))

                    elif event_type == "stop":
                        logger.info(f"Media stream stopped: {self.stream_sid}")
                        break

            except RuntimeError as e:
                # WebSocket was closed (likely by goodbye handler) - this is expected
                if "WebSocket is not connected" in str(e) or "Need to call \"accept\" first" in str(e):
                    print(f"=== TWILIO WEBSOCKET CLOSED (EXPECTED) ===", flush=True)
                    logger.info("Twilio WebSocket closed, exiting message handler")
                else:
                    raise  # Re-raise if it's a different RuntimeError

        except Exception as e:
            logger.error(f"Error handling Twilio messages: {e}", exc_info=True)

    async def _handle_openai_messages(self):
        """Handle incoming messages from OpenAI Realtime API"""
        try:
            print("=== OPENAI HANDLER STARTED ===", flush=True)
            print("=== WAITING FOR OPENAI MESSAGES ===", flush=True)
            async for message in self.openai_ws:
                data = json.loads(message)
                event_type = data.get("type")
                print(f"=== OPENAI MESSAGE: {event_type} ===", flush=True)

                if event_type == "response.audio.delta":
                    # Stream audio back to Twilio
                    audio_data = data.get("delta")
                    if audio_data:
                        if not self.stream_sid:
                            print(f"=== WARNING: stream_sid is None, cannot send audio ===", flush=True)
                        else:
                            await self.twilio_ws.send_json({
                                "event": "media",
                                "streamSid": self.stream_sid,
                                "media": {
                                    "payload": audio_data
                                }
                            })

                elif event_type == "conversation.item.created":
                    # Log conversation items
                    item = data.get("item", {})
                    logger.info(f"Conversation item: {item.get('type')}")

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    # User's speech was transcribed
                    transcript = data.get("transcript", "")
                    if transcript:
                        self.current_user_transcript = transcript
                        print(f"=== USER TRANSCRIPT: {transcript} ===", flush=True)
                        logger.info(f"User said: {transcript}")

                elif event_type == "response.audio_transcript.done":
                    # AI's response transcript is complete
                    transcript = data.get("transcript", "")
                    if transcript:
                        self.current_ai_transcript = transcript
                        print(f"=== AI TRANSCRIPT: {transcript} ===", flush=True)
                        logger.info(f"AI said: {transcript}")

                elif event_type == "response.function_call_arguments.done":
                    # Function call completed - handle it
                    call_id = data.get("call_id")
                    item_id = data.get("item_id")
                    name = data.get("name")
                    arguments = data.get("arguments")

                    print(f"=== FUNCTION CALL: {name} with args {arguments} ===", flush=True)
                    logger.info(f"Function call: {name}({arguments})")

                    try:
                        args = json.loads(arguments)

                        if name == "save_lead_field":
                            # Save the field to the session state
                            field_name = args.get("field_name")
                            field_value = args.get("field_value")

                            if field_name and field_value:
                                # Validate and clean the field value based on field type
                                validation_error = None
                                cleaned_value = field_value

                                if field_name == "zip_code":
                                    # Extract only digits from zip code
                                    zip_digits = "".join(c for c in field_value if c.isdigit())

                                    # Take first 5 digits if ZIP+4 format
                                    if len(zip_digits) > 5:
                                        zip_digits = zip_digits[:5]

                                    # Validate exactly 5 digits
                                    if len(zip_digits) != 5:
                                        validation_error = f"Invalid ZIP code: need exactly 5 digits, got {len(zip_digits)}. Ask user to repeat all 5 digits."
                                        logger.warning(f"ZIP validation failed for '{field_value}': {validation_error}")
                                    else:
                                        # Check for Alaska or Hawaii
                                        if zip_digits.startswith(('995', '996', '997', '998', '999')):
                                            validation_error = "We do not service Alaska. Ask user if they have a different address in the continental US."
                                            logger.warning(f"ZIP validation failed: Alaska ZIP code {zip_digits}")
                                        elif zip_digits.startswith(('967', '968')):
                                            validation_error = "We do not service Hawaii. Ask user if they have a different address in the continental US."
                                            logger.warning(f"ZIP validation failed: Hawaii ZIP code {zip_digits}")
                                        else:
                                            cleaned_value = zip_digits
                                            logger.info(f"ZIP code cleaned: '{field_value}' -> '{cleaned_value}'")

                                if validation_error:
                                    # Return error to AI so it can ask again
                                    await self.openai_ws.send(json.dumps({
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "function_call_output",
                                            "call_id": call_id,
                                            "output": json.dumps({"success": False, "error": validation_error})
                                        }
                                    }))
                                else:
                                    # Update session state with cleaned value
                                    self.session.state[field_name] = cleaned_value
                                    flag_modified(self.session, "state")
                                    self.db.commit()
                                    self.db.refresh(self.session)

                                    print(f"=== SAVED FIELD: {field_name}={cleaned_value} ===", flush=True)
                                    logger.info(f"Saved field: {field_name}={cleaned_value}")

                                    # Track field for turn logging
                                    self.current_turn_fields[field_name] = cleaned_value

                                    # Send success response
                                    await self.openai_ws.send(json.dumps({
                                        "type": "conversation.item.create",
                                        "item": {
                                            "type": "function_call_output",
                                            "call_id": call_id,
                                            "output": json.dumps({"success": True, "message": f"Saved {field_name}"})
                                        }
                                    }))
                            else:
                                logger.warning(f"Invalid save_lead_field arguments: {args}")

                        elif name == "submit_lead":
                            # Submit the lead
                            print(f"=== SUBMITTING LEAD ===", flush=True)
                            logger.info(f"Voice conversation complete - submitting lead for session {self.session.id}")
                            transaction_logger.info(f"Voice conversation complete - session {self.session.id}")

                            # For voice calls, add dummy email if not present
                            # (email collection by voice is too problematic)
                            if not self.session.state.get("email"):
                                # Get phone from state, or fallback to caller_phone
                                phone = self.session.state.get("phone", "") or self.caller_phone or ""
                                # Clean phone number - remove all non-digits
                                phone_digits = "".join(c for c in phone if c.isdigit())

                                if phone_digits:
                                    self.session.state["email"] = f"voice+{phone_digits}@powersportbuyers.com"
                                    flag_modified(self.session, "state")
                                    self.db.commit()
                                    print(f"=== ADDED DUMMY EMAIL FOR VOICE: {self.session.state['email']} ===", flush=True)
                                    logger.info(f"Added dummy email for voice lead: {self.session.state['email']}")
                                else:
                                    logger.warning("Cannot generate dummy email - no phone number available")

                            # Check if all required fields are present
                            miss = missing_fields(self.session.state)
                            if len(miss) == 0:
                                # Submit the lead
                                try:
                                    logger.info(f"Submitting lead to NPA - session {self.session.id}")

                                    # Prepare lead data for NPA API
                                    # Remove sms_consent (internal field, not sent to NPA)
                                    npa_lead_data = dict(self.session.state)
                                    sms_consent = npa_lead_data.pop("sms_consent", None)
                                    logger.info(f"SMS consent for session {self.session.id}: {sms_consent}")

                                    lead_result = await create_lead(npa_lead_data)

                                    # Mark session as closed
                                    self.session.status = "closed"
                                    self.db.commit()
                                    self.db.refresh(self.session)

                                    print(f"=== LEAD SUBMITTED: {lead_result} ===", flush=True)
                                    logger.info(f"Lead successfully submitted to NPA - session {self.session.id}")
                                    transaction_logger.info(f"Lead submitted successfully - session {self.session.id}")

                                    # Save to succeeded_leads table
                                    from .models import SucceededLead
                                    succeeded_lead = SucceededLead(
                                        lead_data=dict(self.session.state),
                                        channel="voice",
                                        session_id=self.session.id,
                                        npa_response=lead_result if isinstance(lead_result, dict) else None
                                    )
                                    self.db.add(succeeded_lead)
                                    self.db.commit()
                                    print(f"=== SAVED TO SUCCEEDED_LEADS TABLE ===", flush=True)

                                except Exception as e:
                                    logger.error(f"Failed to submit lead for session {self.session.id}: {e}", exc_info=True)
                                    transaction_logger.error(f"Lead submission failed - session {self.session.id}: {str(e)}")
                                    print(f"=== LEAD SUBMISSION ERROR: {e} ===", flush=True)

                                    # Save to failed_leads table
                                    from .models import FailedLead
                                    failed_lead = FailedLead(
                                        lead_data=dict(self.session.state),
                                        error_message=str(e),
                                        channel="voice",
                                        session_id=self.session.id
                                    )
                                    self.db.add(failed_lead)
                                    self.db.commit()
                                    print(f"=== SAVED TO FAILED_LEADS TABLE ===", flush=True)

                                # Send success response with explicit instruction to say goodbye
                                await self.openai_ws.send(json.dumps({
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": call_id,
                                        "output": json.dumps({
                                            "success": True,
                                            "message": "Lead submitted successfully. NOW SAY THE GOODBYE MESSAGE: Thank you for your information. An agent will reach out to you within the next 24 hours. Have a great day, goodbye!"
                                        })
                                    }
                                }))

                                # Set flag to hang up after AI says goodbye
                                self.should_hangup_after_next_response = True
                                logger.info("Lead processing complete - will hang up after next AI response")

                            else:
                                logger.warning(f"Cannot submit lead - missing fields: {miss}")
                                await self.openai_ws.send(json.dumps({
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": call_id,
                                        "output": json.dumps({"success": False, "message": f"Missing fields: {miss}"})
                                    }
                                }))

                        # Trigger response after function call
                        await self.openai_ws.send(json.dumps({
                            "type": "response.create"
                        }))

                    except Exception as e:
                        logger.error(f"Error handling function call: {e}", exc_info=True)
                        print(f"=== FUNCTION CALL ERROR: {e} ===", flush=True)

                elif event_type == "response.done":
                    # Response completed
                    logger.info("Response completed")

                    # Log this conversation turn to database
                    if self.current_user_transcript or self.current_ai_transcript:
                        self._log_conversation_turn()

                    # Check if we should hang up after this response (lead was submitted)
                    if self.should_hangup_after_next_response:
                        print("=== LEAD SUBMITTED - HANGING UP AFTER OUTRO ===", flush=True)
                        logger.info("Lead submitted - hanging up after 15 second delay for outro")

                        # Wait 15 seconds for the outro audio to finish playing
                        # This gives enough time for the AI's goodbye message to play
                        await asyncio.sleep(15)

                        print("=== HANGING UP AFTER DELAY ===", flush=True)

                        # Send a mark event to Twilio to signal clean completion
                        try:
                            await self.twilio_ws.send_json({
                                "event": "mark",
                                "streamSid": self.stream_sid,
                                "mark": {
                                    "name": "call_complete"
                                }
                            })
                        except Exception as e:
                            logger.warning(f"Could not send mark event: {e}")

                        # Close the Twilio WebSocket gracefully with normal closure code
                        try:
                            await self.twilio_ws.close(code=1000, reason="call_complete")
                        except Exception as e:
                            logger.warning(f"Error closing Twilio WebSocket: {e}")

                        return

                elif event_type == "input_audio_buffer.speech_started":
                    logger.info("User started speaking")
                    # Optionally interrupt current playback

                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.info("User stopped speaking")

                elif event_type == "error":
                    error_details = json.dumps(data, indent=2)
                    print(f"=== OPENAI ERROR: {error_details} ===", flush=True)
                    logger.error(f"OpenAI error: {data}")

        except Exception as e:
            logger.error(f"Error handling OpenAI messages: {e}", exc_info=True)

    async def cleanup(self):
        """Clean up connections"""
        logger.info(f"Cleaning up media stream for call {self.call_sid}")
        try:
            if self.openai_ws:
                # Check if websocket has a close method and is not already closed
                if hasattr(self.openai_ws, 'close'):
                    # For websockets library, check if connection is open
                    if not (hasattr(self.openai_ws, 'closed') and self.openai_ws.closed):
                        await asyncio.wait_for(self.openai_ws.close(), timeout=2.0)
        except Exception as e:
            logger.warning(f"Error closing OpenAI websocket: {e}")

        try:
            if self.db:
                self.db.close()
        except Exception as e:
            logger.warning(f"Error closing database: {e}")

        logger.info(f"Cleaned up media stream for call {self.call_sid}")
