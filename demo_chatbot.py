
import argparse
import os
import sys
from twilio.rest import Client

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.config import settings
from app.llm import process_turn

def main():
    """
    A CLI chatbot for demonstrating the NPS IVR system.
    """
    parser = argparse.ArgumentParser(description="NPS IVR Demo Chatbot")
    parser.add_argument(
        "--mode",
        choices=["real", "simulate"],
        default="simulate",
        help="Mode of operation: 'real' sends SMS, 'simulate' prints to console.",
    )
    parser.add_argument(
        "--user-phone-number",
        help="The user's phone number (required in 'real' mode).",
    )
    args = parser.parse_args()

    if args.mode == "real" and not args.user_phone_number:
        print("Error: --user-phone-number is required in 'real' mode.")
        sys.exit(1)

    twilio_client = None
    if args.mode == "real":
        if not all([settings.twilio_sid, settings.twilio_auth_token, settings.twilio_phone_number]):
            print("Error: Twilio credentials are not configured in the .env file.")
            sys.exit(1)
        twilio_client = Client(settings.twilio_sid, settings.twilio_auth_token)

    print("Starting NPS IVR Demo Chatbot.")
    print("Type 'quit' to exit.")
    print("-" * 20)

    # Welcome message
    welcome_msg = (
        "Hello! Welcome to National Powersports Auctions. "
        "I'm here to help gather some information about you and your vehicle. "
        "This will only take a few moments. Let's get started!"
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

    state = {}
    done = False

    while not done:
        user_input = input("You: ")
        if user_input.lower() == "quit":
            break

        state, next_q, done = process_turn(user_input, state)

        print(f"Chatbot: {next_q}")

        if args.mode == "real" and twilio_client:
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
    print("Final state:", state)

if __name__ == "__main__":
    main()
