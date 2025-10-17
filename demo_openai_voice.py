#!/usr/bin/env python3
"""
OpenAI Voice Demo - Interactive voice conversation using OpenAI APIs

This demo uses:
- OpenAI Whisper (speech-to-text) for transcription
- OpenAI TTS (text-to-speech) for voice responses
- PyAudio for recording/playback
- Same conversation logic as the main IVR system

Requirements:
    pip install pyaudio openai

Usage:
    python3 demo_openai_voice.py
    python3 demo_openai_voice.py --save-audio  # Save all audio files
    python3 demo_openai_voice.py --no-playback  # Don't play TTS responses (text only)
"""

import argparse
import asyncio
import tempfile
import wave
from pathlib import Path
from typing import Dict, Any, Optional
import sys

try:
    import pyaudio
except ImportError:
    print("❌ PyAudio not installed. Please run: pip install pyaudio")
    print("   On Mac: brew install portaudio && pip install pyaudio")
    sys.exit(1)

from openai import OpenAI
from app.config import settings
from app.llm import process_turn
from app.models import missing_fields


# Audio recording settings
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RECORD_SECONDS = 10  # Maximum recording time
SILENCE_THRESHOLD = 500  # Adjust based on your microphone
SILENCE_DURATION = 2  # Seconds of silence to stop recording


class OpenAIVoiceDemo:
    """Interactive voice demo using OpenAI APIs"""

    def __init__(self, save_audio: bool = False, enable_playback: bool = True):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.save_audio = save_audio
        self.enable_playback = enable_playback
        self.audio_dir = None

        if save_audio:
            self.audio_dir = Path("demo_audio_files")
            self.audio_dir.mkdir(exist_ok=True)
            print(f"📁 Saving audio files to: {self.audio_dir}")

        self.conversation_state: Dict[str, Any] = {}
        self.turn_count = 0

        # Initialize PyAudio
        self.pyaudio = pyaudio.PyAudio()

    def record_audio(self) -> Optional[bytes]:
        """
        Record audio from microphone until silence is detected or max time reached.

        Returns:
            Audio data as bytes, or None if recording failed
        """
        print("\n🎤 Recording... (speak now, will auto-stop after silence)")

        stream = self.pyaudio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        frames = []
        silent_chunks = 0
        max_silent_chunks = int(SILENCE_DURATION * RATE / CHUNK)
        started_speaking = False

        try:
            for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

                # Calculate volume (simple amplitude check)
                amplitude = sum(abs(int.from_bytes(data[i:i+2], 'little', signed=True))
                               for i in range(0, len(data), 2)) / (len(data) // 2)

                if amplitude > SILENCE_THRESHOLD:
                    started_speaking = True
                    silent_chunks = 0
                elif started_speaking:
                    silent_chunks += 1

                    if silent_chunks > max_silent_chunks:
                        print("🔇 Silence detected, stopping recording")
                        break

        except KeyboardInterrupt:
            print("\n⚠️  Recording interrupted")
            return None
        finally:
            stream.stop_stream()
            stream.close()

        if not frames:
            return None

        # Convert to WAV format
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
            wf = wave.open(temp_wav.name, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pyaudio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

            # Read back as bytes
            with open(temp_wav.name, 'rb') as f:
                audio_data = f.read()

            # Save if requested
            if self.save_audio and self.audio_dir:
                save_path = self.audio_dir / f"recording_{self.turn_count:03d}.wav"
                with open(save_path, 'wb') as f:
                    f.write(audio_data)
                print(f"💾 Saved recording to: {save_path}")

            return audio_data

    def transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """
        Transcribe audio using OpenAI Whisper.

        Args:
            audio_data: Audio file data as bytes

        Returns:
            Transcribed text, or None if transcription failed
        """
        print("🔄 Transcribing with OpenAI Whisper...")

        try:
            # Write to temporary file (Whisper API requires file)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            # Transcribe
            with open(temp_path, 'rb') as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",
                    prompt="This is a conversation about selling powersports vehicles like motorcycles, ATVs, Harley-Davidson, Yamaha, Kawasaki."
                )

            # Clean up temp file
            Path(temp_path).unlink()

            return transcription.text

        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return None

    def synthesize_speech(self, text: str) -> Optional[bytes]:
        """
        Synthesize speech using OpenAI TTS.

        Args:
            text: Text to convert to speech

        Returns:
            Audio data as bytes, or None if synthesis failed
        """
        print("🔄 Generating speech with OpenAI TTS...")

        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
                input=text,
                speed=1.0
            )

            # Get audio data
            audio_data = response.content

            # Save if requested
            if self.save_audio and self.audio_dir:
                save_path = self.audio_dir / f"response_{self.turn_count:03d}.mp3"
                with open(save_path, 'wb') as f:
                    f.write(audio_data)
                print(f"💾 Saved TTS response to: {save_path}")

            return audio_data

        except Exception as e:
            print(f"❌ TTS error: {e}")
            return None

    def play_audio(self, audio_data: bytes):
        """
        Play audio using PyAudio.

        Args:
            audio_data: MP3 audio data from OpenAI TTS
        """
        if not self.enable_playback:
            return

        try:
            # Convert MP3 to WAV using pydub (requires ffmpeg)
            try:
                from pydub import AudioSegment
                from pydub.playback import play

                # Write to temp file
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                    temp_file.write(audio_data)
                    temp_path = temp_file.name

                # Load and play
                audio = AudioSegment.from_mp3(temp_path)
                print("🔊 Playing response...")
                play(audio)

                # Clean up
                Path(temp_path).unlink()

            except ImportError:
                print("⚠️  pydub not installed. Install with: pip install pydub")
                print("   Also requires ffmpeg: brew install ffmpeg (Mac) or apt-get install ffmpeg (Linux)")
                print("   Skipping playback...")

        except Exception as e:
            print(f"⚠️  Playback error: {e}")

    def run_conversation(self):
        """Run the interactive voice conversation"""
        print("\n" + "="*60)
        print("🎙️  OpenAI Voice Demo - NPA Lead Intake")
        print("="*60)
        print("\nThis demo uses OpenAI's Whisper (STT) and TTS APIs")
        print("to simulate a voice conversation for lead collection.")
        print("\nPress Ctrl+C at any time to exit.\n")

        # Welcome message
        welcome = "Thank you for calling National Powersport Buyers, where we make selling your powersport vehicle stress free. I am an AI assistant and I will start the process of selling your vehicle. What's your first name?"
        print(f"\n🤖 Assistant: {welcome}\n")

        # Generate and play welcome TTS
        welcome_audio = self.synthesize_speech(welcome)
        if welcome_audio:
            self.play_audio(welcome_audio)

        # Main conversation loop
        done = False
        last_asked_field = "first_name"

        while not done:
            try:
                self.turn_count += 1

                # Record user input
                audio_data = self.record_audio()
                if not audio_data:
                    print("⚠️  No audio recorded, please try again.")
                    continue

                # Transcribe
                user_text = self.transcribe_audio(audio_data)
                if not user_text:
                    print("⚠️  Transcription failed, please try again.")
                    continue

                print(f"\n👤 You said: {user_text}")

                # Process turn
                new_state, next_q, done = process_turn(
                    user_text,
                    self.conversation_state,
                    last_asked_field
                )

                # Update state
                self.conversation_state = new_state

                # Determine what field we're asking about next
                if not done:
                    miss = missing_fields(new_state)
                    if miss:
                        last_asked_field = miss[0]

                # Display response
                print(f"\n🤖 Assistant: {next_q}")

                # Synthesize and play response
                response_audio = self.synthesize_speech(next_q)
                if response_audio:
                    self.play_audio(response_audio)

                # Show collected information
                print("\n" + "-"*60)
                print("📋 Collected Information:")
                for field, value in sorted(self.conversation_state.items()):
                    if not field.startswith("_"):
                        print(f"   {field}: {value}")
                print("-"*60 + "\n")

                if done:
                    print("\n✅ Conversation complete!")
                    print("\n📊 Final Lead Information:")
                    for field, value in sorted(self.conversation_state.items()):
                        if not field.startswith("_"):
                            print(f"   • {field}: {value}")
                    print("\n")
                    break

            except KeyboardInterrupt:
                print("\n\n⚠️  Demo interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()
                break

        # Cleanup
        self.pyaudio.terminate()
        print("\n👋 Demo ended. Thank you!\n")


def main():
    parser = argparse.ArgumentParser(
        description="OpenAI Voice Demo - Interactive lead intake conversation"
    )
    parser.add_argument(
        "--save-audio",
        action="store_true",
        help="Save all audio files (recordings and TTS responses) to demo_audio_files/"
    )
    parser.add_argument(
        "--no-playback",
        action="store_true",
        help="Don't play TTS responses (text only mode)"
    )

    args = parser.parse_args()

    # Check for required dependencies
    print("\n🔍 Checking dependencies...")

    missing_deps = []

    try:
        import pyaudio
        print("✅ PyAudio installed")
    except ImportError:
        missing_deps.append("pyaudio")

    try:
        from pydub import AudioSegment
        print("✅ pydub installed")
    except ImportError:
        print("⚠️  pydub not installed (optional, for audio playback)")
        print("   Install with: pip install pydub")
        print("   Also requires: brew install ffmpeg (Mac)")

    if missing_deps:
        print(f"\n❌ Missing required dependencies: {', '.join(missing_deps)}")
        print("\nInstallation instructions:")
        print("  Mac:")
        print("    brew install portaudio")
        print("    pip install pyaudio pydub")
        print("    brew install ffmpeg")
        print("\n  Linux:")
        print("    sudo apt-get install portaudio19-dev python3-pyaudio ffmpeg")
        print("    pip install pyaudio pydub")
        sys.exit(1)

    if not settings.openai_api_key:
        print("\n❌ OPENAI_API_KEY not set in environment")
        print("   Please set it in your .env file or environment")
        sys.exit(1)

    print("✅ All dependencies ready\n")

    # Run demo
    demo = OpenAIVoiceDemo(
        save_audio=args.save_audio,
        enable_playback=not args.no_playback
    )
    demo.run_conversation()


if __name__ == "__main__":
    main()
