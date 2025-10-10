#!/usr/bin/env python3
"""Quick test to verify OpenAI API key works."""

import sys
import os
import json

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.config import settings
from app.llm import client, FIELD_PRETTY
from openai import OpenAI

def test_with_debug():
    """Test with full debug output."""
    print("Testing OpenAI integration with debug output...")
    print(f"API Key configured: {bool(settings.openai_api_key)}")
    print(f"Model: {settings.openai_model}")
    print()

    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set in .env file")
        return

    # Test message
    test_message = "Hi, my name is Tim and I'm selling a 2018 Harley Davidson"
    state = {}

    print(f"Test message: '{test_message}'")
    print(f"Current state: {state}")
    print()

    # Create the prompt
    sys_prompt = (
        "You are a lead intake assistant for National Powersports Auctions (NPA). "
        "From the user's message, extract any of these fields if present: first_name, last_name, address, phone, email, vehicle_make, vehicle_model, vehicle_year. "
        "IMPORTANT: For the 'address' field, we only need the STATE of residence. If the user provides a full address, extract only the state abbreviation or name. "
        "IMPORTANT: When the user provides a short direct answer (like just 'Smith' or 'John'), use the conversation context to infer which field they're answering. "
        "Look at the known_state to see what fields are still missing and what was likely just asked. "
        "For example, if last_name is missing and they say 'Smith', extract it as last_name: 'Smith'. "
        "Then propose one short, friendly next question that asks for the most important missing field. "
        "Use conversational variety - don't repeat the exact same phrasing. Be natural and friendly while gathering the required information. "
        "You can rephrase questions in different ways (e.g., 'Could you share your first name?' vs 'What's your first name?' vs 'May I have your first name?'). "
        "Return STRICT JSON with keys exactly as above, plus next_question."
    )

    user_payload = {
        "known_state": state,
        "message": test_message,
        "required_fields": list(FIELD_PRETTY.keys()),
    }

    print("=" * 60)
    print("SYSTEM PROMPT:")
    print(sys_prompt)
    print()
    print("USER PAYLOAD:")
    print(json.dumps(user_payload, indent=2))
    print("=" * 60)
    print()

    try:
        print("Calling OpenAI API...")
        resp = client().chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        text = resp.choices[0].message.content or "{}"
        print("✓ SUCCESS!")
        print()
        print("=" * 60)
        print("RAW OPENAI RESPONSE:")
        print(text)
        print("=" * 60)
        print()

        data = json.loads(text)
        print("PARSED JSON:")
        print(json.dumps(data, indent=2))
        print()

        # Extract fields
        extracted = {k: data.get(k) for k in FIELD_PRETTY.keys() if data.get(k)}
        next_q = data.get("next_question")

        print("EXTRACTED FIELDS:")
        print(json.dumps(extracted, indent=2))
        print()
        print(f"NEXT QUESTION: {next_q}")

    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_with_debug()
