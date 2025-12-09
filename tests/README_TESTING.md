# Testing Strategy for NPS IVR

This document explains the different types of tests and how they would have caught the critical voice data loss bug.

## Test Types

### 1. Unit Tests (`test_voice_integration.py`)
**Speed**: Fast (milliseconds)
**When to run**: On every commit, in CI/CD
**What they test**: Individual components in isolation

These tests use **mocking** to test handler logic without real connections:
- ✅ Database operations (real DB writes)
- ✅ Session management logic
- ✅ Data persistence logic
- ❌ NO real WebSocket connections
- ❌ NO real OpenAI API calls
- ❌ NO audio processing

**Example:**
```python
def test_function_call_saves_field_to_database(self):
    """Test that save_lead_field actually saves to database"""
    handler.session.state["full_name"] = "John Doe"
    # Verify it's in the database
```

**Would have caught:**
- ✅ Voice data not being saved to database
- ✅ Session reuse bug (session 72)
- ✅ Missing conversation turn logging
- ✅ Closed sessions being reused

### 2. End-to-End Tests (`test_voice_e2e.py`)
**Speed**: Slow (seconds to minutes)
**When to run**: Before deployments, nightly builds
**What they test**: Full system integration

These tests connect to the **running server** and simulate real calls:
- ✅ Real WebSocket connections
- ✅ Real server endpoints
- ✅ Real database writes
- ✅ Full conversation flow
- ⚠️ Uses simulated audio (not real OpenAI calls by default)

**Example:**
```python
async def test_full_voice_call_saves_data(self):
    """Connect to running server and simulate call"""
    async with websockets.connect(WS_URL) as ws:
        # Send Twilio start event
        # Simulate audio
        # Verify database
```

**Would have caught:**
- ✅ Voice data not saved in production environment
- ✅ WebSocket connection issues
- ✅ Full pipeline integration problems
- ✅ Deployment configuration issues

### 3. Database Verification Tests (`test_voice_e2e.py::TestDatabaseVerification`)
**Speed**: Fast
**When to run**: Hourly in production (monitoring)
**What they test**: Production database state

These tests can run against **production database** (read-only) to detect issues:

**Example:**
```python
def test_recent_voice_calls_have_data(self):
    """Check last hour of calls for data loss"""
    sessions = get_recent_voice_sessions()
    success_rate = sessions_with_data / total
    assert success_rate >= 0.8  # 80% threshold
```

**Would have caught:**
- ✅ **60/63 calls with no data** (would trigger immediately!)
- ✅ Session reuse in production
- ✅ Missing conversation turns
- ✅ Data loss trends over time

This is the test that would have **immediately alerted** us to the bug!

## How to Run Tests

### Run Unit Tests (Fast)
```bash
# All unit tests
python3 -m pytest tests/test_voice_integration.py -v

# Critical bug tests only
python3 -m pytest tests/test_voice_integration.py::TestCriticalBugScenarios -v

# Single test
python3 -m pytest tests/test_voice_integration.py::TestCriticalBugScenarios::test_voice_call_must_save_data -v
```

### Run E2E Tests (Requires Running Server)
```bash
# Start server first
uvicorn app.main:app --reload --port 8000

# In another terminal, run E2E tests
python3 -m pytest tests/test_voice_e2e.py::TestDatabaseVerification -v
```

### Run Production Monitoring Tests
```bash
# Run against production database (read-only)
python3 -m pytest tests/test_voice_e2e.py::TestDatabaseVerification::test_recent_voice_calls_have_data -v

# Set up as cron job (run every hour)
0 * * * * cd /path/to/nps_ivr && python3 -m pytest tests/test_voice_e2e.py::TestDatabaseVerification -v >> /var/log/voice_monitoring.log 2>&1
```

## What Each Test Would Have Caught

### The Critical Bug: 60/63 Calls with No Data

#### Unit Test Detection:
```python
def test_voice_call_must_save_data(self):
    """WOULD HAVE FAILED"""
    # Simulates voice call
    handler.save_field("full_name", "John")
    # Checks database
    assert session.state["full_name"] == "John"  # ❌ WOULD FAIL
```
**Result**: ❌ Test fails because `save_field()` function didn't exist

#### E2E Test Detection:
```python
async def test_full_voice_call_saves_data(self):
    """WOULD HAVE FAILED"""
    # Makes real call to running server
    await simulate_voice_call()
    # Checks database
    assert session.state is not None  # ❌ WOULD FAIL
```
**Result**: ❌ Test fails because database shows empty state

#### Production Monitoring Detection:
```python
def test_recent_voice_calls_have_data(self):
    """WOULD HAVE FAILED"""
    success_rate = 3/63  # Only 3 had data
    assert success_rate >= 0.8  # ❌ WOULD FAIL (4.7% vs 80%)
```
**Result**: ❌ **Alert triggered immediately** when monitoring ran!

### Session Reuse Bug (All Calls Using Session 72)

#### Unit Test:
```python
def test_each_call_unique_session(self):
    """WOULD HAVE FAILED"""
    session1 = create_handler("call_1").get_session()
    session2 = create_handler("call_2").get_session()
    assert session1.id != session2.id  # ❌ WOULD FAIL (both = 72)
```

#### Production Monitoring:
```python
def test_no_session_reuse(self):
    """WOULD HAVE FAILED"""
    call_sids = [s.session_key for s in recent_sessions]
    # All would be "pending"
    assert len(call_sids) == len(set(call_sids))  # ❌ WOULD FAIL
```

## Test Coverage Matrix

| Test Type | Speed | Catches Logic Bugs | Catches Integration Bugs | Catches Production Issues | CI/CD | Production Monitoring |
|-----------|-------|-------------------|-------------------------|--------------------------|-------|---------------------|
| Unit Tests | ⚡ Fast | ✅ Yes | ❌ No | ❌ No | ✅ Yes | ❌ No |
| E2E Tests | 🐌 Slow | ✅ Yes | ✅ Yes | ⚠️ Partial | ⚠️ Optional | ❌ No |
| DB Verification | ⚡ Fast | ❌ No | ❌ No | ✅ **YES** | ❌ No | ✅ **YES** |

## Recommended Testing Strategy

### Development (Before Commit)
```bash
# Quick smoke test
python3 -m pytest tests/test_voice_integration.py::TestCriticalBugScenarios -v
```

### CI/CD Pipeline
```bash
# All unit tests
python3 -m pytest tests/test_voice_integration.py -v

# Code coverage
python3 -m pytest tests/test_voice_integration.py --cov=app --cov-report=html
```

### Pre-Deployment
```bash
# Full E2E test suite
python3 -m pytest tests/test_voice_e2e.py -v --run-e2e
```

### Production Monitoring (Hourly Cron)
```bash
# Data loss detection
python3 -m pytest tests/test_voice_e2e.py::TestDatabaseVerification::test_recent_voice_calls_have_data -v

# Send alert if fails
|| curl -X POST https://alerts.company.com/critical \
   -d '{"alert": "Voice data loss detected"}'
```

## How to Add Voice Synthesis for True E2E Tests

To create a **fully realistic E2E test** with actual audio:

### Option 1: Google TTS (Recommended)
```python
from google.cloud import texttospeech

def text_to_ulaw_audio(text: str) -> str:
    """Convert text to µ-law encoded audio"""
    client = texttospeech.TextToSpeechClient()

    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Standard-C"
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MULAW,
        sample_rate_hertz=8000
    )

    response = client.synthesize_speech(
        input=input_text,
        voice=voice,
        audio_config=audio_config
    )

    return base64.b64encode(response.audio_content).decode('ascii')

# Use in test:
async def test_with_real_tts():
    audio = text_to_ulaw_audio("My name is John Doe")
    await websocket.send_audio(audio)
```

### Option 2: Record Real Audio
```bash
# Record test phrases
ffmpeg -i test_audio.wav -ar 8000 -ac 1 -f mulaw test_audio.ulaw

# Use in test
with open('test_audio.ulaw', 'rb') as f:
    audio_data = base64.b64encode(f.read()).decode('ascii')
```

## Critical Test That Would Have Saved Us

**This single test run hourly would have caught the bug immediately:**

```python
@pytest.mark.production_monitoring
def test_recent_voice_calls_have_data(self, db_session):
    """Run this hourly in production!"""
    recent_sessions = get_last_hour_voice_calls()

    sessions_with_data = sum(
        1 for s in recent_sessions
        if s.state and len(s.state) > 1
    )

    success_rate = sessions_with_data / len(recent_sessions)

    # 80% threshold - if less, trigger alert
    if success_rate < 0.8:
        send_alert(f"CRITICAL: Voice data loss! Only {success_rate:.1%} success")

    assert success_rate >= 0.8
```

**On October 24, 2025 at 2:22 PM**, this test would have:
- ❌ Failed with: "CRITICAL: Voice data loss! Only 4.7% success (3/63)"
- 🚨 Triggered immediate alert
- 🔧 We would have fixed it same day
- 💰 60 leads would not have been lost

## Summary

1. **Unit tests** (`test_voice_integration.py`) - Fast, catch logic bugs
2. **E2E tests** (`test_voice_e2e.py`) - Slow, catch integration bugs
3. **DB monitoring tests** - **CRITICAL**, would have caught production bug immediately

**The bug would have been caught within 1 hour** if we had the production monitoring test running!
