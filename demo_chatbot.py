
import argparse
import os
import sys
import xml.etree.ElementTree as ET
from twilio.rest import Client
from fastapi.testclient import TestClient

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.config import settings
from app.main import app

def extract_message_from_twiml(twiml_str: str) -> str:
    """Extract the message text from TwiML response."""
    try:
        root = ET.fromstring(twiml_str)
        # Find the Message element (could be Response/Message or just Message)
        msg_elem = root.find('.//Message')
        if msg_elem is not None and msg_elem.text:
            return msg_elem.text.strip()
        return ""
    except Exception:
        return ""

def main():
    """
    A CLI chatbot for demonstrating the NPS IVR system.
    """
    parser = argparse.ArgumentParser(description="NPS IVR Demo Chatbot")
    parser.add_argument(
        "--mode",
        choices=["real", "simulate", "webhook"],
        default="simulate",
        help="Mode of operation: 'real' sends SMS via Twilio, 'simulate' prints to console, 'webhook' calls SMS webhook directly.",
    )
    parser.add_argument(
        "--user-phone-number",
        help="The user's phone number (required in 'real' and 'webhook' modes).",
    )
    args = parser.parse_args()

    if args.mode in ["real", "webhook"] and not args.user_phone_number:
        print(f"Error: --user-phone-number is required in '{args.mode}' mode.")
        sys.exit(1)

    twilio_client = None
    if args.mode == "real":
        if not all([settings.twilio_sid, settings.twilio_auth_token, settings.twilio_phone_number]):
            print("Error: Twilio credentials are not configured in the .env file.")
            sys.exit(1)
        twilio_client = Client(settings.twilio_sid, settings.twilio_auth_token)

    # Create test client for webhook mode
    test_client = TestClient(app) if args.mode == "webhook" else None

    print(f"Starting NPS IVR Demo Chatbot (mode: {args.mode}).")
    print("Type 'quit' to exit.")
    print("-" * 20)

    # Generate a unique session ID for this conversation
    import uuid
    session_id = f"SMS{uuid.uuid4().hex[:8]}"

    if args.mode == "webhook":
        # In webhook mode, we make an initial call to simulate receiving first message
        # This will trigger the welcome flow and pre-populate phone from caller ID
        print("(Making initial webhook call to start conversation)")
        initial_response = test_client.post(
            "/twilio/sms",
            data={
                "From": args.user_phone_number,
                "To": settings.twilio_phone_number or "+15557654321",
                "Body": "Hi",
                "SmsSid": session_id,
            }
        )
        welcome_msg = extract_message_from_twiml(initial_response.text)
        print(f"Chatbot: {welcome_msg}")
        print("-" * 20)
    else:
        # Welcome message for non-webhook modes
        welcome_msg = (
            "Hi! Welcome to National Powersports Auctions. "
            "We help you sell your powersports vehicles. "
            "I'll help you get started. What's your first name?"
        )
        print(f"Chatbot: {welcome_msg}")
        if args.mode == "real" and twilio_client:
            try:
                message = twilio_client.messages.create(
                    body=welcome_msg,
                    from_=settings.twilio_phone_number,
                    to=args.user_phone_number,
                )
                print(f"(SMS sent to {args.user_phone_number}, SID: {message.sid})")
            except Exception as e:
                print(f"(Error sending SMS: {e})")
        elif args.mode == "simulate":
            print(f"(Simulating SMS to {args.user_phone_number or 'N/A'})")
        print("-" * 20)

    done = False

    while not done:
        try:
            user_input = input("You: ")
        except EOFError:
            print("\n(Input closed, exiting)")
            break

        if user_input.lower() == "quit":
            break

        if args.mode == "webhook":
            # Make actual webhook call
            response = test_client.post(
                "/twilio/sms",
                data={
                    "From": args.user_phone_number,
                    "To": settings.twilio_phone_number or "+15557654321",
                    "Body": user_input,
                    "SmsSid": session_id,
                }
            )
            next_q = extract_message_from_twiml(response.text)

            # Check if conversation is done (completion message)
            if "thank you" in next_q.lower() and "submitted" in next_q.lower():
                done = True
        else:
            # Use process_turn for simulate/real modes (legacy behavior)
            from app.llm import process_turn
            from app.db import SessionLocal
            from app.main import get_or_create_session

            # Get session to maintain state
            db = SessionLocal()
            try:
                session = get_or_create_session(
                    db, "sms", session_id,
                    args.user_phone_number if args.mode == "real" else "+15551234567",
                    settings.twilio_phone_number or "+15557654321"
                )

                # Pre-populate phone from caller ID on first turn
                current_state = session.state or {}
                if not current_state and args.mode == "real" and args.user_phone_number:
                    from app.main import extract_caller_phone
                    caller_phone, _ = extract_caller_phone(args.user_phone_number)
                    if caller_phone:
                        current_state["phone"] = caller_phone
                        print(f"(Pre-populated phone from caller ID: {caller_phone})")

                new_state, next_q, done = process_turn(user_input, current_state)
                session.state = new_state
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(session, "state")
                db.commit()
            finally:
                db.close()

        print(f"Chatbot: {next_q}")

        if args.mode == "real" and twilio_client and next_q:
            try:
                message = twilio_client.messages.create(
                    body=next_q,
                    from_=settings.twilio_phone_number,
                    to=args.user_phone_number,
                )
                print(f"(SMS sent to {args.user_phone_number}, SID: {message.sid})")
            except Exception as e:
                print(f"(Error sending SMS: {e})")
        elif args.mode == "simulate":
            print(f"(Simulating SMS to {args.user_phone_number or 'N/A'})")

        print("-" * 20)

    print("Conversation finished.")

if __name__ == "__main__":
    main()
