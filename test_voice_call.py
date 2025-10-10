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

        # Use a valid-looking test phone number for caller ID detection
        # Note: The system will detect this and ask for confirmation
        test_from_number = "+17203811084"

        print(f"📞 Simulating call from: {test_from_number}")
        print(f"   (System will detect and ask for confirmation)\n")

        # Initial call to /twilio/voice
        response = requests.post(
            f"{self.base_url}/twilio/voice",
            data={
                "CallSid": self.call_sid,
                "From": test_from_number,  # Valid format for caller ID detection
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
        max_retries = 3
        retry_count = 0
        interrupt_count = 0  # Track consecutive Ctrl+C presses

        while not done:
            try:
                # Listen for user input
                user_input = self.listen(timeout=10)

                # Reset interrupt counter on successful input
                if user_input:
                    interrupt_count = 0

                # Check for exit command
                if user_input and user_input.lower().strip() in ["exit", "quit", "bye", "goodbye"]:
                    print("\n[EXIT COMMAND] Terminating call as requested.\n")
                    break

                if not user_input:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"\nNo input received after {max_retries} attempts. Ending call.\n")
                        break
                    print(f"No input received. Trying again... (Attempt {retry_count}/{max_retries})\n")
                    continue

                # Reset retry count on successful input
                retry_count = 0

                # Send to /twilio/voice/collect
                # Note: The server will handle:
                #   - Phone number confirmation (if phone number is detected)
                #   - Email confirmation (if email is detected)
                #   - Email domain auto-correction (gmail, yahoo, etc.)
                #   - Field validation with helpful voice-friendly error messages
                response = requests.post(
                    f"{self.base_url}/twilio/voice/collect",
                    data={
                        "CallSid": self.call_sid,
                        "From": "+17203811084",  # Must match the start_call From number
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

            except KeyboardInterrupt:
                interrupt_count += 1
                if interrupt_count == 1:
                    print("\n\n[INTERRUPTED] Press Ctrl+C again to exit, or Ctrl+D to quit immediately.\n")
                    continue
                else:
                    print("\n\n[EXITING] Call terminated by user.\n")
                    break
            except EOFError:
                # Ctrl+D pressed
                print("\n\n[EXITING] Call terminated by user (Ctrl+D).\n")
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
    print("\nNew Features Being Tested:")
    print("  ✓ Caller ID detection and phone confirmation")
    print("  ✓ Phone number read-back and confirmation")
    print("  ✓ Email address read-back and confirmation")
    print("  ✓ Auto-correction for common domains (gmail, yahoo, etc.)")
    print("  ✓ Voice-friendly validation error messages")
    print("\nTips:")
    print("  - Speak clearly when prompted")
    print("  - For email: say 'at' for @ and 'dot' for periods")
    print("    Example: 'john at gmail dot com'")
    print("  - You can also say 'john at gmail' (auto-corrects to .com)")
    print("  - When asked to confirm, say 'yes' or 'no'")
    print("  - Say 'exit', 'quit', or 'bye' to end the call")
    print("  - Press Ctrl+C during listening to skip input")
    print("  - Press Ctrl+C twice (or Ctrl+D once) to exit the simulator")
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
