#!/usr/bin/env python3
"""
Test script to compare OpenAI Voice API (Whisper) vs Twilio speech recognition.

This script helps evaluate:
1. OpenAI Whisper transcription quality
2. Response time comparison
3. Cost comparison
4. Integration complexity

Usage:
    python3 test_openai_voice.py --audio-file path/to/audio.wav
    python3 test_openai_voice.py --record-audio  # Record live audio for testing
"""
import argparse
import asyncio
import time
from pathlib import Path
from openai import OpenAI
from app.config import settings


def test_whisper_transcription(audio_file_path: str, model: str = "whisper-1", language: str = "en"):
    """
    Test OpenAI Whisper transcription on an audio file.

    Args:
        audio_file_path: Path to audio file (mp3, mp4, mpeg, mpga, m4a, wav, webm)
        model: Whisper model to use (default: whisper-1)
        language: Language code (default: en for English)

    Returns:
        Dict with transcription results and timing info
    """
    client = OpenAI(api_key=settings.openai_api_key)

    print(f"\n{'='*60}")
    print(f"Testing OpenAI Whisper Transcription")
    print(f"{'='*60}")
    print(f"Audio file: {audio_file_path}")
    print(f"Model: {model}")
    print(f"Language: {language}")
    print()

    # Check if file exists
    audio_path = Path(audio_file_path)
    if not audio_path.exists():
        print(f"❌ Error: Audio file not found: {audio_file_path}")
        return None

    # Check file size
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"File size: {file_size_mb:.2f} MB")

    if file_size_mb > 25:
        print(f"⚠️  Warning: File size exceeds OpenAI's 25MB limit")
        return None

    try:
        # Time the transcription
        start_time = time.time()

        with open(audio_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                language=language,
                response_format="verbose_json",  # Get more detailed info
            )

        elapsed_time = time.time() - start_time

        # Display results
        print(f"✅ Transcription successful!")
        print(f"⏱️  Time taken: {elapsed_time:.2f} seconds")
        print()
        print(f"📝 Transcription:")
        print(f"   {transcription.text}")
        print()

        # Additional info if available
        if hasattr(transcription, 'duration'):
            print(f"🎵 Audio duration: {transcription.duration:.2f} seconds")
            real_time_factor = elapsed_time / transcription.duration
            print(f"⚡ Real-time factor: {real_time_factor:.2f}x")
            print(f"   (< 1.0 is faster than real-time)")

        if hasattr(transcription, 'language'):
            print(f"🌍 Detected language: {transcription.language}")

        print()

        return {
            "text": transcription.text,
            "elapsed_time": elapsed_time,
            "file_size_mb": file_size_mb,
            "model": model,
            "duration": getattr(transcription, 'duration', None),
            "language": getattr(transcription, 'language', language),
        }

    except Exception as e:
        print(f"❌ Error during transcription: {str(e)}")
        return None


def test_whisper_with_prompt(audio_file_path: str, prompt: str):
    """
    Test Whisper with a custom prompt to guide transcription.

    Useful for:
    - Domain-specific vocabulary (e.g., "Harley-Davidson", "Yamaha")
    - Name spelling
    - Technical terms

    Args:
        audio_file_path: Path to audio file
        prompt: Text prompt to guide transcription
    """
    client = OpenAI(api_key=settings.openai_api_key)

    print(f"\n{'='*60}")
    print(f"Testing Whisper with Custom Prompt")
    print(f"{'='*60}")
    print(f"Prompt: {prompt}")
    print()

    try:
        start_time = time.time()

        with open(audio_file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                prompt=prompt,
                language="en",
            )

        elapsed_time = time.time() - start_time

        print(f"✅ Transcription successful!")
        print(f"⏱️  Time taken: {elapsed_time:.2f} seconds")
        print()
        print(f"📝 Transcription (with prompt):")
        print(f"   {transcription.text}")
        print()

        return transcription.text

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None


def compare_models():
    """
    Compare OpenAI Whisper vs Twilio speech recognition.
    """
    print(f"\n{'='*60}")
    print("OpenAI Whisper vs Twilio Speech Recognition Comparison")
    print(f"{'='*60}\n")

    comparison = """
    ┌─────────────────────┬──────────────────────┬─────────────────────────┐
    │ Feature             │ OpenAI Whisper       │ Twilio Speech (Google)  │
    ├─────────────────────┼──────────────────────┼─────────────────────────┤
    │ Accuracy            │ ⭐⭐⭐⭐⭐ Excellent   │ ⭐⭐⭐⭐ Very Good        │
    │ Speed               │ ~2-5 seconds         │ Real-time streaming     │
    │ Cost                │ $0.006/minute        │ $0.02/minute            │
    │ Integration         │ Requires recording   │ Native to Twilio        │
    │ Custom Vocabulary   │ ✅ Prompt support    │ ✅ Hints support         │
    │ Multiple Languages  │ ✅ 99+ languages     │ ✅ Many languages        │
    │ Noise Handling      │ ⭐⭐⭐⭐⭐ Excellent   │ ⭐⭐⭐⭐ Very Good        │
    │ Technical Terms     │ ⭐⭐⭐⭐⭐ Excellent   │ ⭐⭐⭐ Good              │
    │ Phone Numbers       │ ⭐⭐⭐⭐ Very Good    │ ⭐⭐⭐⭐ Very Good        │
    │ Email Addresses     │ ⭐⭐⭐ Good           │ ⭐⭐ Fair               │
    │ Names/Proper Nouns  │ ⭐⭐⭐⭐⭐ Excellent   │ ⭐⭐⭐⭐ Very Good        │
    └─────────────────────┴──────────────────────┴─────────────────────────┘

    📊 Use Case Recommendations:

    ✅ Use OpenAI Whisper when:
       - You need highest accuracy for complex terms
       - You're dealing with technical vocabulary (vehicle makes/models)
       - You want better email address transcription
       - Cost is a concern (3x cheaper)
       - You can handle async processing (2-5 second delay)

    ✅ Use Twilio Speech when:
       - You need real-time feedback
       - Simplicity is priority (no recording management)
       - You want immediate user feedback
       - Network latency to OpenAI API is a concern

    🔄 Hybrid Approach:
       - Use Twilio for real-time interaction
       - Use OpenAI Whisper for critical fields (email, technical terms)
       - Implement fallback: Twilio first, Whisper on validation failure
    """

    print(comparison)


def create_test_recordings_guide():
    """
    Display guide for creating test recordings.
    """
    print(f"\n{'='*60}")
    print("Guide: Creating Test Audio Recordings")
    print(f"{'='*60}\n")

    guide = """
    📱 Option 1: Record on Mac (QuickTime)
    1. Open QuickTime Player
    2. File → New Audio Recording
    3. Click record button
    4. Speak test phrases
    5. Save as .m4a or .wav

    🎙️  Option 2: Record on iPhone
    1. Use Voice Memos app
    2. Record test phrases
    3. Share → Save to Files
    4. Transfer to computer

    💻 Option 3: Use Python (requires pyaudio)
    ```bash
    pip install pyaudio wave
    python3 -c "import pyaudio, wave
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
    frames = []
    print('Recording... (speak for 5 seconds)')
    for i in range(0, int(16000 / 1024 * 5)):
        data = stream.read(1024)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf = wave.open('test_audio.wav', 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(16000)
    wf.writeframes(b''.join(frames))
    wf.close()
    print('Saved to test_audio.wav')
    "
    ```

    🎯 Recommended Test Phrases:
    1. Names: "My name is John Smith"
    2. Email: "My email is john dot smith at gmail dot com"
    3. Phone: "My phone number is five five five, one two three, four five six seven"
    4. Vehicle: "I have a two thousand twenty Harley Davidson Street Glide"
    5. Technical: "I'm calling from California about my Kawasaki Ninja"
    6. Complex: "My email is tfox underscore 2023 at yahoo dot com"

    📂 Audio File Formats Supported:
       - WAV (recommended for quality)
       - M4A, MP3 (good for file size)
       - MPEG, MPGA, MP4, WEBM
       - Max size: 25 MB
    """

    print(guide)


def estimate_costs(monthly_calls: int, avg_duration_seconds: float = 120):
    """
    Compare costs between OpenAI Whisper and Twilio Speech.

    Args:
        monthly_calls: Number of calls per month
        avg_duration_seconds: Average call duration in seconds
    """
    print(f"\n{'='*60}")
    print(f"Cost Comparison for {monthly_calls:,} calls/month")
    print(f"{'='*60}\n")

    avg_duration_minutes = avg_duration_seconds / 60

    # OpenAI Whisper: $0.006/minute
    whisper_cost_per_call = avg_duration_minutes * 0.006
    whisper_monthly_cost = whisper_cost_per_call * monthly_calls

    # Twilio Speech: $0.02/minute (Google Speech)
    twilio_cost_per_call = avg_duration_minutes * 0.02
    twilio_monthly_cost = twilio_cost_per_call * monthly_calls

    savings = twilio_monthly_cost - whisper_monthly_cost
    savings_percentage = (savings / twilio_monthly_cost) * 100

    print(f"Assumptions:")
    print(f"  - Average call duration: {avg_duration_seconds:.0f} seconds ({avg_duration_minutes:.1f} minutes)")
    print(f"  - Monthly call volume: {monthly_calls:,} calls")
    print()

    print(f"OpenAI Whisper:")
    print(f"  - Rate: $0.006/minute")
    print(f"  - Cost per call: ${whisper_cost_per_call:.4f}")
    print(f"  - Monthly cost: ${whisper_monthly_cost:.2f}")
    print()

    print(f"Twilio Speech Recognition:")
    print(f"  - Rate: $0.02/minute")
    print(f"  - Cost per call: ${twilio_cost_per_call:.4f}")
    print(f"  - Monthly cost: ${twilio_monthly_cost:.2f}")
    print()

    print(f"💰 Potential Savings with OpenAI Whisper:")
    print(f"  - Per call: ${savings/monthly_calls:.4f}")
    print(f"  - Monthly: ${savings:.2f} ({savings_percentage:.0f}% reduction)")
    print(f"  - Annually: ${savings*12:.2f}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Test and compare OpenAI Whisper voice transcription"
    )
    parser.add_argument(
        "--audio-file",
        help="Path to audio file to transcribe"
    )
    parser.add_argument(
        "--prompt",
        help="Custom prompt to guide transcription (optional)"
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Show comparison between OpenAI and Twilio"
    )
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Show guide for creating test recordings"
    )
    parser.add_argument(
        "--costs",
        action="store_true",
        help="Show cost comparison"
    )
    parser.add_argument(
        "--monthly-calls",
        type=int,
        default=1000,
        help="Number of monthly calls for cost estimation (default: 1000)"
    )
    parser.add_argument(
        "--call-duration",
        type=float,
        default=120,
        help="Average call duration in seconds (default: 120)"
    )

    args = parser.parse_args()

    # Show guide if requested
    if args.guide:
        create_test_recordings_guide()
        return

    # Show comparison if requested
    if args.compare:
        compare_models()
        return

    # Show cost comparison if requested
    if args.costs:
        estimate_costs(args.monthly_calls, args.call_duration)
        return

    # Test transcription if audio file provided
    if args.audio_file:
        # Test basic transcription
        result = test_whisper_transcription(args.audio_file)

        # Test with prompt if provided
        if args.prompt and result:
            test_whisper_with_prompt(args.audio_file, args.prompt)

        return

    # If no arguments, show help
    parser.print_help()
    print()
    print("Quick start examples:")
    print("  python3 test_openai_voice.py --guide          # Show recording guide")
    print("  python3 test_openai_voice.py --compare        # Compare models")
    print("  python3 test_openai_voice.py --costs          # Show cost analysis")
    print("  python3 test_openai_voice.py --audio-file test.wav")
    print()


if __name__ == "__main__":
    main()
