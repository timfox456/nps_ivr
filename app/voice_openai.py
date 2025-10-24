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
SYSTEM_INSTRUCTIONS = """You are a friendly AI assistant for National Powersport Buyers, where we make selling your powersport vehicle stress free.

Start by saying: "Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle."

Then collect the following information from the caller:
1. Full name
2. ZIP code (5 digits)
3. Phone number
4. Email address
5. Vehicle information: year, make, and model (example: "2000 Yamaha Grizzly")
   - If they give you all three together (like "2000 Yamaha Grizzly"), extract year, make, and model separately
   - If they only give partial info, ask for what's missing

CRITICAL CONFIRMATION RULES:
- PHONE NUMBER from Caller ID: If confirming caller ID number and they say "yes", just move on - NO CONFIRMATION NEEDED
- PHONE NUMBER spoken by user: ALWAYS confirm by reading back digit by digit: "Let me confirm, that's 4-7-0-8-0-7-3-3-1-7, is that correct?"
- ZIP CODE: ALWAYS confirm by reading digit by digit: "Let me confirm your ZIP code, that's 3-0-0-9-3, is that correct?"
- EMAIL: First acknowledge what you heard, then confirm using NATO phonetic alphabet. Example:
  * User says: "T-F-O-X at yahoo dot com"
  * You say: "I heard T-F-O-X at yahoo dot com. Let me confirm that's T as in Tango, F as in Foxtrot, O as in Oscar, X as in X-ray at yahoo dot com. Is that correct?"
  * IMPORTANT: Only use phonetic alphabet in YOUR confirmation, not when initially hearing it
- Use NATO alphabet for confirmation: Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel, India, Juliet, Kilo, Lima, Mike, November, Oscar, Papa, Quebec, Romeo, Sierra, Tango, Uniform, Victor, Whiskey, X-ray, Yankee, Zulu
- If user repeats email multiple times or seems frustrated, acknowledge and confirm more carefully

Be conversational and natural. Ask one question at a time.
If the caller provides multiple pieces of information at once, acknowledge what you heard and ask for the next missing field.
Be patient and helpful if they need clarification.

When you have all the information, thank them and let them know an agent will contact them within 24 hours.
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
                    "silence_duration_ms": 500
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
                        caller_id_message = f"SYSTEM INFO: The caller is calling from {phone_speech}. After your greeting, ask them: 'I see you're calling from {phone_speech}. Is this the best number to reach you?' If they say yes, record the phone as {caller_phone} and do NOT repeat the number back - simply move on to the next question. If they say no, ask for the correct number and confirm it digit by digit."

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

                        # Trigger a response
                        await self.openai_ws.send(json.dumps({
                            "type": "response.create"
                        }))

                        print(f"=== SENT CALLER ID TO OPENAI ===", flush=True)

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
                print(f"=== OPENAI MESSAGE RECEIVED ===", flush=True)
                data = json.loads(message)
                event_type = data.get("type")

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

                elif event_type == "input_audio_buffer.speech_started":
                    logger.info("User started speaking")
                    # Optionally interrupt current playback

                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.info("User stopped speaking")

                elif event_type == "error":
                    logger.error(f"OpenAI error: {data}")

        except Exception as e:
            logger.error(f"Error handling OpenAI messages: {e}", exc_info=True)

    async def cleanup(self):
        """Clean up connections"""
        logger.info(f"Cleaning up media stream for call {self.call_sid}")
        try:
            if self.openai_ws and not self.openai_ws.closed:
                await asyncio.wait_for(self.openai_ws.close(), timeout=2.0)
        except Exception as e:
            logger.warning(f"Error closing OpenAI websocket: {e}")

        try:
            if self.db:
                self.db.close()
        except Exception as e:
            logger.warning(f"Error closing database: {e}")

        logger.info(f"Cleaned up media stream for call {self.call_sid}")
