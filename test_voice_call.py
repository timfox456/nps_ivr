#!/usr/bin/env python3
"""
Voice call simulator for testing the NPA IVR system.
Uses computer microphone for input and speakers for output.
"""

import argparse
import os
import sys
import time
import tempfile
from pathlib import Path

try:
    import speech_recognition as sr
    from gtts import gTTS
    import pygame
    import requests
except ImportError:
    print("Missing dependencies. Install with:")
    print("pip install SpeechRecognition gtts pygame requests pyaudio")
    sys.exit(1)

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app.config import settings


class VoiceCallSimulator:
    """Simulates a voice call to test the IVR system."""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.call_sid = f"TEST_CALL_{int(time.time())}"
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        pygame.mixer.init()

        # Adjust for ambient noise
        print("Calibrating microphone for ambient noise... Please wait.")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Microphone ready!")

    def speak(self, text):
        """Convert text to speech and play it."""
        print(f"\n[IVR SAYS]: {text}\n")

        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                temp_file = fp.name

            # Generate speech
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(temp_file)

            # Play audio
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            # Wait for audio to finish
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            # Clean up
            pygame.mixer.music.unload()
            os.unlink(temp_file)

        except Exception as e:
            print(f"Error playing audio: {e}")

    def listen(self, timeout=10):
        """Listen to microphone and return transcribed text."""
        print("[LISTENING...] Speak now (or press Ctrl+C to skip)")

        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)

            print("[PROCESSING...] Transcribing your speech...")
            text = self.recognizer.recognize_google(audio)
            print(f"[YOU SAID]: {text}\n")
            return text

        except sr.WaitTimeoutError:
            print("[TIMEOUT] No speech detected.\n")
            return ""
        except sr.UnknownValueError:
            print("[ERROR] Could not understand audio.\n")
            return ""
        except sr.RequestError as e:
            print(f"[ERROR] Speech recognition error: {e}\n")
            return ""
        except KeyboardInterrupt:
            print("\n[SKIPPED]\n")
            return ""

    def start_call(self):
        """Initiate the call to /twilio/voice endpoint."""
        print(f"\n{'='*60}")
        print(f"Starting simulated voice call...")
        print(f"Call SID: {self.call_sid}")
        print(f"{'='*60}\n")

        # Initial call to /twilio/voice
        response = requests.post(
            f"{self.base_url}/twilio/voice",
            data={
                "CallSid": self.call_sid,
                "From": "+15555555555",  # Test number
                "To": settings.twilio_phone_number or "+16198530829",
            }
        )

        if response.status_code != 200:
            print(f"Error: Server returned {response.status_code}")
            print(response.text)
            return

        # Parse TwiML response to extract the message
        twiml = response.text
        message = self._extract_say_text(twiml)

        if message:
            self.speak(message)

        # Continue the conversation loop
        self.conversation_loop()

    def conversation_loop(self):
        """Main conversation loop."""
        done = False

        while not done:
            # Listen for user input
            user_input = self.listen(timeout=10)

            if not user_input:
                print("No input received. Trying again...\n")
                continue

            # Send to /twilio/voice/collect
            response = requests.post(
                f"{self.base_url}/twilio/voice/collect",
                data={
                    "CallSid": self.call_sid,
                    "From": "+15555555555",
                    "To": settings.twilio_phone_number or "+16198530829",
                    "SpeechResult": user_input,
                }
            )

            if response.status_code != 200:
                print(f"Error: Server returned {response.status_code}")
                print(response.text)
                break

            # Parse TwiML response
            twiml = response.text
            message = self._extract_say_text(twiml)

            # Check if call should end
            if "<Hangup/>" in twiml or "<Hangup />" in twiml:
                done = True
                if message:
                    self.speak(message)
                print("\n[CALL ENDED]")
                break

            # Speak the response
            if message:
                self.speak(message)
            else:
                print("No response from server. Ending call.")
                break

        print(f"\n{'='*60}")
        print("Call simulation complete!")
        print(f"{'='*60}\n")

    def _extract_say_text(self, twiml):
        """Extract text from <Say> tags in TwiML."""
        import re

        # Simple regex to extract text from <Say> tags
        matches = re.findall(r'<Say[^>]*>(.*?)</Say>', twiml, re.DOTALL | re.IGNORECASE)

        if matches:
            # Join all Say elements and clean up
            text = ' '.join(matches)
            # Remove any nested XML tags
            text = re.sub(r'<[^>]+>', '', text)
            return text.strip()

        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Voice call simulator for testing NPA IVR system"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the FastAPI server (default: http://localhost:8000)"
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("NPA IVR Voice Call Simulator")
    print("="*60)
    print("\nThis tool simulates a voice call using your computer's")
    print("microphone and speakers to test the IVR system locally.")
    print("\nRequirements:")
    print("  - Working microphone")
    print("  - Working speakers/headphones")
    print("  - Internet connection (for speech recognition)")
    print("\nTips:")
    print("  - Speak clearly when prompted")
    print("  - Press Ctrl+C during listening to skip")
    print("  - Use 'quit' or hang up to end the call")
    print("="*60 + "\n")

    try:
        simulator = VoiceCallSimulator(base_url=args.url)
        simulator.start_call()
    except KeyboardInterrupt:
        print("\n\nCall interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
