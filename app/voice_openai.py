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

logger = logging.getLogger(__name__)

# OpenAI Realtime API configuration
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
OPENAI_MODEL = "gpt-4o-realtime-preview-2024-10-01"

# System instructions for the AI assistant
SYSTEM_INSTRUCTIONS = """You are a friendly AI assistant for PowerSportBuyers.com, where we make selling your powersport vehicle stress free.

Start by saying: "Thank you for calling Power Sport Buyers dot com, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle."

Then collect the following information from the caller:
1. Full name
2. ZIP code (MUST be exactly 5 digits)
3. Phone number
4. Vehicle information: year, make, and model (example: "2000 Yamaha Grizzly")
   - If they give you all three together (like "2000 Yamaha Grizzly"), extract year, make, and model separately
   - If they only give partial info, ask for what's missing

NOTE: Do NOT ask for email address over the phone - we will collect that later.

ZIP CODE VALIDATION RULES:
- ZIP code MUST be exactly 5 digits
- If caller provides 4 digits or less, ask them to provide all 5 digits
- If caller provides ZIP+4 format (9 digits like "30093-1234" or "300931234"), only use the first 5 digits and ignore the extra 4
- CRITICAL: We do NOT service Alaska or Hawaii
  * Alaska ZIP codes start with: 995, 996, 997, 998, or 999
  * Hawaii ZIP codes start with: 967 or 968
  * If caller provides an Alaska or Hawaii ZIP code, politely say: "I'm sorry, we don't currently service [Alaska/Hawaii]. We only service the continental United States at this time."
  * DO NOT accept Alaska or Hawaii ZIP codes
- ALWAYS confirm the 5-digit ZIP code by reading it back digit by digit BEFORE checking if it's Alaska/Hawaii

CRITICAL CONFIRMATION RULES - ALWAYS CONFIRM THESE FIELDS:
- FULL NAME: ALWAYS confirm by repeating it back: "Let me confirm, that's [First Name] [Last Name], is that correct?"
  * If they say NO or correct you, say "I apologize, what is the correct name?" and re-ask for their full name
  * After getting the correction, confirm it again before moving on
- PHONE NUMBER from Caller ID: If confirming caller ID number and they say "yes", just move on - NO CONFIRMATION NEEDED
- PHONE NUMBER spoken by user: ALWAYS confirm by reading back digit by digit: "Let me confirm, that's 4-7-0-8-0-7-3-3-1-7, is that correct?"
  * If they say NO, say "I apologize, let me get that again. What's your phone number?" and re-ask
  * Confirm the corrected number digit by digit before moving on
- ZIP CODE: ALWAYS confirm by reading the 5 digits back digit by digit: "Let me confirm your ZIP code, that's 3-0-0-9-3, is that correct?"
  * If they say NO, say "I apologize, what is your correct ZIP code?" and re-ask
  * Confirm the corrected ZIP code before moving on
- VEHICLE INFORMATION: ALWAYS confirm year, make, and model: "Let me confirm, that's a [Year] [Make] [Model], is that correct?"
  * If they say NO, say "I apologize, what is the correct year, make, and model?" and re-ask
  * Confirm the corrected information before moving on
- If user repeats any information multiple times or seems frustrated, acknowledge and confirm more carefully

CRITICAL: When user corrects information after you confirm it, you MUST re-ask for that same field and confirm it again. DO NOT move on to the next field until the current field is correctly confirmed.

Be conversational and natural. Ask one question at a time.
If the caller provides multiple pieces of information at once, acknowledge what you heard and ask for the next missing field.
Be patient and helpful if they need clarification.

HANDLING UNCLEAR OR NO RESPONSES:
- If you hear silence, background noise, or unclear speech, say "I'm sorry, I didn't catch that. Could you please repeat?"
- If caller says "hello?" or "are you there?", respond with "Yes, I'm here! Let me continue..." and repeat your last question
- Never get stuck waiting - always ask a clarifying question if you're unsure what the caller said

When you have all the information, say EXACTLY: "Thank you for your information. An agent will reach out to you within the next 24 hours. Have a great day, goodbye!"
"""


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

    async def start(self):
        """Start handling the media stream"""
        try:
            print(f"=== HANDLER START: call_sid={self.call_sid} ===", flush=True)
            logger.info(f"Starting media stream handler for call {self.call_sid}")

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
            await asyncio.gather(
                self._handle_twilio_messages(),
                self._handle_openai_messages()
            )

        except Exception as e:
            logger.error(f"Error in media stream handler: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()

    def _get_or_create_session(self) -> ConversationSession:
        """Get or create conversation session"""
        obj = (
            self.db.query(ConversationSession)
            .filter(
                ConversationSession.channel == "voice",
                ConversationSession.session_key == self.call_sid
            )
            .first()
        )
        if obj:
            return obj
        obj = ConversationSession(
            channel="voice",
            session_key=self.call_sid,
            from_number=None,  # Will be set from Twilio metadata
            to_number=None,
            state={}
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
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

CRITICAL PRONUNCIATION: When saying the phone number, speak each digit SEPARATELY with a brief pause between each one. For example, say "nine... six... one... eight... three... eight..." NOT "nine hundred sixty one" or "nine sixty one". Each digit must be said individually.

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
                    "threshold": 0.6,  # Increased from 0.5 to reduce false triggers (0.0-1.0, higher = less sensitive)
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 700  # Increased from 500ms to 700ms to require longer silence before considering speech done
                }
            }
        }))

        logger.info(f"Connected to OpenAI Realtime API for call {self.call_sid}")

    async def _handle_twilio_messages(self):
        """Handle incoming messages from Twilio Media Stream"""
        try:
            print(f"=== TWILIO HANDLER STARTED: stream_sid={self.stream_sid} ===", flush=True)
            logger.info(f"Starting to handle Twilio messages for stream {self.stream_sid}")
            print("=== WAITING FOR TWILIO MESSAGES ===", flush=True)
            async for message in self.twilio_ws.iter_text():
                print(f"=== TWILIO MESSAGE RECEIVED ===", flush=True)
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "start":
                    # Extract stream info and custom parameters
                    self.stream_sid = data["start"]["streamSid"]
                    self.call_sid = data["start"]["callSid"]

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

                elif event_type == "response.done":
                    # Response completed
                    logger.info("Response completed")

                    # Check if this response contains the call completion marker
                    response = data.get("response", {})
                    output = response.get("output", [])
                    for item in output:
                        if item.get("type") == "message":
                            content = item.get("content", [])
                            for c in content:
                                # Check both text and audio transcript fields
                                text = ""
                                if c.get("type") == "text":
                                    text = c.get("text", "")
                                elif c.get("type") == "audio":
                                    text = c.get("transcript", "")

                                # Look for the goodbye message to detect call completion
                                if text and ("Have a great day, goodbye" in text or "have a great day, goodbye" in text.lower()):
                                    print("=== GOODBYE MESSAGE DETECTED - CALL COMPLETE ===", flush=True)
                                    logger.info("Goodbye message detected - will hangup after 20 second delay")

                                    # Wait 20 seconds for the goodbye audio to finish playing
                                    await asyncio.sleep(20)

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
