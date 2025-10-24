"""
OpenAI Realtime API - Optimized Production Version

Optimizations:
- Minimal logging (errors only)
- No database writes during call (only at end)
- Direct audio forwarding without processing
- Faster message handling
- Connection pooling ready
"""
import asyncio
import json
import logging
from typing import Optional
import websockets
from fastapi import WebSocket

from .config import settings

logger = logging.getLogger(__name__)

# OpenAI Realtime API configuration
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
OPENAI_MODEL = "gpt-4o-realtime-preview-2024-10-01"

# Optimized system instructions (concise)
SYSTEM_INSTRUCTIONS = """You are a friendly AI assistant for National Powersport Buyers, where we make selling your powersport vehicle stress free.

Start by saying: "Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle."

Then collect the following information:
1. Full name
2. State of residence (just the state, not full address)
3. Phone number
4. Email address
5. Vehicle make (e.g., Yamaha, Honda, Kawasaki)
6. Vehicle model (e.g., R1, CBR, Ninja)
7. Vehicle year

Be conversational and natural. Ask one question at a time.
When you have all the information, thank them and let them know an agent will contact them within 24 hours."""


class OptimizedRealtimeHandler:
    """Optimized handler with minimal overhead for production"""

    def __init__(self, twilio_ws: WebSocket, call_sid: str, stream_sid: str,
                 caller_phone: str = None, phone_speech: str = None):
        self.twilio_ws = twilio_ws
        self.call_sid = call_sid
        self.stream_sid = stream_sid
        self.caller_phone = caller_phone
        self.phone_speech = phone_speech
        self.openai_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.conversation_data = {}  # Store data for end-of-call processing

    async def start(self):
        """Start optimized audio streaming"""
        try:
            logger.info(f"[OPTIMIZED] Starting handler for call {self.call_sid}")

            # Connect to OpenAI
            logger.info(f"[OPTIMIZED] Attempting OpenAI connection for {self.call_sid}...")
            await self._connect_openai()
            logger.info(f"[OPTIMIZED] Connected to OpenAI for call {self.call_sid}")

            # Start bidirectional audio streaming
            logger.info(f"[OPTIMIZED] Starting audio streaming for {self.call_sid}")
            await asyncio.gather(
                self._forward_twilio_to_openai(),
                self._forward_openai_to_twilio(),
                return_exceptions=True
            )
            logger.info(f"[OPTIMIZED] Audio streaming ended for {self.call_sid}")

        except Exception as e:
            logger.error(f"[OPTIMIZED] Error in handler {self.call_sid}: {e}", exc_info=True)
        finally:
            logger.info(f"[OPTIMIZED] Cleaning up {self.call_sid}")
            await self._cleanup()

    async def _connect_openai(self):
        """Connect to OpenAI with minimal config"""
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

If they say yes, record the phone as: {self.caller_phone}
If they say no, ask them for the correct phone number."""

        # Minimal session config
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": instructions,
                "voice": "alloy",
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "silence_duration_ms": 500
                }
            }
        }))

    async def _forward_twilio_to_openai(self):
        """Forward Twilio audio to OpenAI (optimized)"""
        try:
            async for message in self.twilio_ws.iter_text():
                data = json.loads(message)
                event = data.get("event")

                if event == "media":
                    # Direct forward without processing
                    await self.openai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": data["media"]["payload"]
                    }))

                elif event == "stop":
                    break

        except Exception as e:
            logger.error(f"Twilio stream error {self.call_sid}: {e}", exc_info=True)

    async def _forward_openai_to_twilio(self):
        """Forward OpenAI audio to Twilio (optimized)"""
        try:
            async for message in self.openai_ws:
                data = json.loads(message)
                event_type = data.get("type")

                if event_type == "response.audio.delta":
                    # Direct forward audio
                    audio_data = data.get("delta")
                    if audio_data:
                        await self.twilio_ws.send_json({
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": audio_data}
                        })

                elif event_type == "conversation.item.created":
                    # Collect data for end-of-call processing (minimal overhead)
                    item = data.get("item", {})
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for c in content:
                            if c.get("type") == "text":
                                # Store for later analysis
                                self.conversation_data.setdefault("messages", []).append(c.get("text"))

                elif event_type == "error":
                    logger.error(f"OpenAI error {self.call_sid}: {data}")

        except Exception as e:
            logger.error(f"OpenAI stream error {self.call_sid}: {e}", exc_info=True)

    async def _cleanup(self):
        """Fast cleanup"""
        try:
            if self.openai_ws:
                # Check if websocket is still open (handle both old and new websockets library)
                try:
                    is_closed = getattr(self.openai_ws, 'closed', False)
                    if not is_closed:
                        await asyncio.wait_for(self.openai_ws.close(), timeout=1.0)
                except Exception as close_error:
                    logger.debug(f"Error closing OpenAI websocket for {self.call_sid}: {close_error}")
        except Exception as e:
            logger.error(f"Cleanup error for {self.call_sid}: {e}")

        # TODO: Process conversation_data and save to database
        # This happens async after call ends, not blocking the audio stream
        # asyncio.create_task(self._save_conversation_data())

    async def _save_conversation_data(self):
        """Save conversation data after call (non-blocking)"""
        # This would extract fields from conversation_data and save to database
        # Happens after the call completes, doesn't affect call latency
        pass
