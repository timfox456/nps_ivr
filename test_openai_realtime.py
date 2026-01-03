#!/usr/bin/env python3
"""Test OpenAI Realtime API connection"""
import asyncio
import websockets
import json
from app.config import settings

async def test_openai_connection():
    """Test connecting to OpenAI Realtime API"""
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "OpenAI-Beta": "realtime=v1"
    }

    print(f"Connecting to OpenAI Realtime API...")
    print(f"URL: {url}")

    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            print("✅ Connected successfully!")

            # Send session update
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": "You are a helpful assistant.",
                    "voice": "alloy"
                }
            }))
            print("✅ Sent session.update")

            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=5.0)
            data = json.loads(response)
            print(f"✅ Received: {data.get('type')}")

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed with status {e.status_code}")
        print(f"   Headers: {e.headers}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_openai_connection())
