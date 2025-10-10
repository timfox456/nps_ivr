# Testing Voice Confirmation Features

This guide helps you test the new phone and email confirmation features in the voice workflow.

## Overview of New Features

The system now includes:

1. **Caller ID Detection & Confirmation** - Detects phone number from caller ID and asks for confirmation
2. **Phone Number Confirmation** - Reads back phone numbers and asks user to confirm
3. **Email Address Confirmation** - Reads back email addresses and asks user to confirm
4. **Email Domain Auto-Correction** - Automatically adds `.com` to common domains (gmail, yahoo, hotmail, outlook, icloud, aol)
5. **Voice-Friendly Validation** - Better error messages designed for text-to-speech

## Quick Start

### 1. Start the Development Server

```bash
# Terminal 1: Start FastAPI server
source .venv/bin/activate
uv run uvicorn app.main:app --reload --port 8000
```

### 2. Run the Voice Call Simulator

```bash
# Terminal 2: Run the test script
python3 test_voice_call.py
```

The simulator will:
- Use your computer's microphone to capture your voice
- Use Google Speech Recognition to transcribe your speech
- Send the transcription to the FastAPI server
- Play the IVR responses through your speakers using text-to-speech

## Testing Scenarios

### Scenario 1: Caller ID Phone Confirmation

**What happens:**
1. System detects caller ID: `+15551234567`
2. System asks: "I see you're calling from 555-123-4567. Is this the best number to reach you?"
3. You respond: "yes" or "no"

**To test:**
- Say **"yes"** - System saves the phone and continues to first name
- Say **"no"** - System asks for your phone number
- Say something unclear - System repeats the question

### Scenario 2: Phone Number Read-Back

**What happens:**
1. When system asks for phone number
2. You say: "555-223-4567" or "five five five two two three four five six seven"
3. System reads back: "I heard your phone number is 555, 223, 4567. Is that correct?"
4. You confirm: "yes" or "no"

**To test:**
```
IVR: "What is the best phone number to reach you?"
YOU: "555-223-4567"
IVR: "I heard your phone number is 555, 223, 4567. Is that correct?"
YOU: "yes"
```

**Try these responses:**
- ✅ "yes" / "yeah" / "correct" / "right" - Saves number and continues
- ❌ "no" / "nope" / "wrong" - Asks for phone again
- ❓ "maybe" / "what" - Repeats the confirmation question

### Scenario 3: Email Address Read-Back

**What happens:**
1. When system asks for email
2. You say: "john at gmail dot com"
3. System reads back: "I heard your email is john at gmail dot com. Is that correct?"
4. You confirm: "yes" or "no"

**To test:**
```
IVR: "What is your email address?"
YOU: "john at gmail dot com"
IVR: "I heard your email is john at gmail dot com. Is that correct?"
YOU: "yes"
```

**Email Speaking Patterns:**
- "at" = @
- "dot" = .
- "dash" or "hyphen" = -
- "underscore" = _

**Examples:**
- "john at gmail dot com" → john@gmail.com
- "john dot smith at yahoo dot com" → john.smith@yahoo.com
- "user underscore 123 at company dash mail dot org" → user_123@company-mail.org

### Scenario 4: Email Domain Auto-Correction

**What happens:**
1. You say incomplete domain: "john at gmail"
2. System auto-corrects to: "john@gmail.com"
3. System reads back: "john at gmail dot com"

**To test:**
```
IVR: "What is your email address?"
YOU: "john at gmail"
IVR: "I heard your email is john at gmail dot com. Is that correct?"
YOU: "yes"
```

**Supported domains:**
- gmail → gmail.com
- yahoo → yahoo.com
- hotmail → hotmail.com
- outlook → outlook.com
- icloud → icloud.com
- aol → aol.com
- protonmail → protonmail.com
- msn → msn.com

### Scenario 5: Invalid Email Detection

**What happens:**
1. You say something that's not a valid email: "john yahoo" (missing 'at')
2. System detects invalid format
3. System asks you to try again with helpful message

**To test:**
```
IVR: "What is your email address?"
YOU: "john yahoo"
IVR: "Sorry, I didn't hear the 'at' symbol in your email address. Could you please provide your Email again?"
YOU: "john at yahoo dot com"
```

**Invalid cases the system catches:**
- Missing @ symbol: "john gmail dot com"
- Missing domain: "john at"
- Missing dot in domain: "john at gmail"
- Too short: "a@b"

### Scenario 6: Complete Flow Test

Test the entire conversation from start to finish:

```
IVR: "Hi! Welcome to National Powersports Auctions. I see you're calling from 555-123-4567. Is this the best number to reach you?"
YOU: "yes"

IVR: "Great! Now, what's your first name?"
YOU: "John"

IVR: "What is your last name?"
YOU: "Doe"

IVR: "What state do you reside in?"
YOU: "California"

IVR: "I heard your phone number is 555, 123, 4567. Is that correct?"
YOU: "yes"

IVR: "Got it. What is your email address?"
YOU: "john at gmail"

IVR: "I heard your email is john at gmail dot com. Is that correct?"
YOU: "yes"

IVR: "Perfect. What is the make of the vehicle?"
YOU: "Honda"

IVR: "What is the model of the vehicle?"
YOU: "Civic"

IVR: "What is the year of the vehicle?"
YOU: "2020"

IVR: "Thank you. Your information has been submitted to N P A. Goodbye."
[Call ends]
```

## Troubleshooting

### Speech Recognition Issues

**Problem:** Script can't understand your voice

**Solutions:**
- Speak more clearly and slowly
- Move closer to the microphone
- Reduce background noise
- Check microphone permissions
- Ensure good internet connection (uses Google Speech Recognition)

### Audio Playback Issues

**Problem:** Can't hear the IVR responses

**Solutions:**
- Check speaker/headphone volume
- Verify pygame is installed: `pip install pygame`
- Check system audio settings
- Try restarting the script

### Server Connection Issues

**Problem:** "Error: Server returned 500"

**Solutions:**
- Ensure FastAPI server is running: `curl http://localhost:8000/health`
- Check server logs in Terminal 1
- Verify `.env` file has required variables:
  - `OPENAI_API_KEY`
  - `TWILIO_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_PHONE_NUMBER`

### Confirmation Loop Issues

**Problem:** System keeps asking for confirmation even after saying "yes"

**Solutions:**
- Say "yes" more clearly
- Try alternatives: "yeah", "correct", "right"
- Check speech recognition transcription in console
- If stuck, press Ctrl+C and restart

## Checking the Database

After a test call, verify the data was saved correctly:

```bash
sqlite3 nps_ivr.db

# View the most recent session
SELECT * FROM conversation_sessions ORDER BY created_at DESC LIMIT 1;

# View the state JSON
SELECT
    id,
    channel,
    json_extract(state, '$.first_name') as first_name,
    json_extract(state, '$.phone') as phone,
    json_extract(state, '$.email') as email,
    status
FROM conversation_sessions
ORDER BY created_at DESC
LIMIT 1;
```

**What to verify:**
- ✓ Phone number is in format: `(555) 123-4567`
- ✓ Email is valid: `john@gmail.com`
- ✓ Status is `closed` (completed)
- ✓ All required fields are present

## Running Unit Tests

The features are covered by comprehensive unit tests:

```bash
# Run all tests
uv run pytest tests/ -v

# Run only voice confirmation tests
uv run pytest tests/test_voice_confirmation.py -v

# Run only validation tests (includes auto-correction)
uv run pytest tests/test_validation.py -v
```

**Expected results:**
- 88 tests total
- All tests should pass
- Includes 18 new tests for confirmation and auto-correction features

## Testing with Real Twilio

To test with an actual phone call:

1. **Set up ngrok:**
   ```bash
   ngrok http 8000
   ```

2. **Update Twilio webhooks:**
   - Voice webhook: `POST https://YOUR-NGROK-URL.ngrok.io/twilio/voice`
   - Use Twilio Console or CLI

3. **Call your Twilio number:**
   - The system will detect your caller ID
   - Follow the prompts as in the simulator

4. **Monitor:**
   - Check ngrok web interface: http://localhost:4040
   - Check FastAPI logs in terminal
   - Check Twilio debugger: https://console.twilio.com/monitor/debugger

## Known Limitations

1. **Speech Recognition Accuracy**
   - Google Speech Recognition may mishear words
   - Background noise affects accuracy
   - Accents may cause transcription errors
   - Test in a quiet environment for best results

2. **Text-to-Speech Quality**
   - gTTS (Google Text-to-Speech) has robotic voice
   - Some words may be pronounced oddly
   - Real Twilio TTS sounds more natural

3. **Confirmation Logic**
   - Only "yes/no" type responses work for confirmation
   - System looks for keywords: "yes", "yeah", "no", "nope", etc.
   - Ambiguous responses trigger re-asking

## Tips for Best Results

1. **Clear Speech:** Enunciate clearly, especially for email addresses
2. **Quiet Environment:** Background noise interferes with recognition
3. **Good Microphone:** Use a quality microphone, not built-in laptop mic
4. **Internet Connection:** Stable connection needed for Google APIs
5. **Patience:** Wait for the full prompt before speaking
6. **Confirmation:** Always listen to the read-back carefully before confirming

## Next Steps

After testing:

1. **Review the session data** in SQLite to ensure fields are captured correctly
2. **Check validation** - try invalid emails/phones to see error handling
3. **Test edge cases** - very long emails, special characters, etc.
4. **Document any issues** you find
5. **Test with real calls** via Twilio once local testing passes

## Support

If you encounter issues:
- Check the FastAPI server logs (Terminal 1)
- Check the test script console output (Terminal 2)
- Review the database: `sqlite3 nps_ivr.db`
- Check Twilio debugger (for real calls)
- Review code changes in `app/main.py` and `app/validation.py`
