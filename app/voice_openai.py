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
2. State of residence (just the state, not full address)
3. Phone number
4. Email address
5. Vehicle make (e.g., Yamaha, Honda, Kawasaki)
6. Vehicle model (e.g., R1, CBR, Ninja)
7. Vehicle year

Be conversational and natural. Ask one question at a time.
If the caller provides multiple pieces of information at once, acknowledge what you heard and ask for the next missing field.
Be patient and helpful if they need clarification.

When you have all the information, thank them and let them know an agent will contact them within 24 hours.
"""


class TwilioMediaStreamHandler:
    """Handles Twilio Media Stream WebSocket connection and OpenAI Realtime API"""

    def __init__(self, twilio_ws: WebSocket, call_sid: str, stream_sid: str = None):
        self.twilio_ws = twilio_ws
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.openai_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session: Optional[ConversationSession] = None
        self.db: Optional[Session] = None

    async def start(self):
        """Start handling the media stream"""
        try:
            logger.info(f"Starting media stream handler for call {self.call_sid}")

            # Get or create database session
            self.db = SessionLocal()
            logger.info("Database session created")

            self.session = self._get_or_create_session()
            logger.info(f"Conversation session ready: {self.session.id}")

            # Connect to OpenAI Realtime API
            logger.info("Attempting to connect to OpenAI Realtime API...")
            await self._connect_to_openai()
            logger.info("Successfully connected to OpenAI Realtime API")

            # Start handling messages from both Twilio and OpenAI
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

        # Configure the session
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": SYSTEM_INSTRUCTIONS,
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
            logger.info(f"Starting to handle Twilio messages for stream {self.stream_sid}")
            async for message in self.twilio_ws.iter_text():
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "start":
                    # Already handled in main endpoint, but just in case
                    self.stream_sid = data["start"]["streamSid"]
                    logger.info(f"Media stream started: {self.stream_sid}")

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
            async for message in self.openai_ws:
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
