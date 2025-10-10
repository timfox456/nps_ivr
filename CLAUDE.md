# NPA IVR - Claude Code Assistant Guide

## Quick Context

This is a FastAPI application that provides SMS and Voice webhook endpoints for Twilio, collecting lead information for National Powersports Auctions (NPA) using OpenAI for conversational field extraction.

**Current State:**
- Active Twilio phone: +16198530829
- Using Python 3.11.13 with uv package manager
- SQLite database at `./nps_ivr.db`
- OpenAI model: gpt-4o-mini (configurable)

## File References for Common Tasks

### When working on webhooks/endpoints
- **Primary file:** `app/main.py:55-130` (SMS and Voice webhook handlers)
- **Session management:** `app/main.py:29-41` (get_or_create_session function)

### When working on LLM/conversation logic
- **Primary file:** `app/llm.py:46-103` (extract_and_prompt, process_turn)
- **Field definitions:** `app/models.py:23-46` (REQUIRED_FIELDS, FIELD_PRETTY)

### When working on configuration
- **Settings class:** `app/config.py:4-27`
- **Environment:** `.env:1-4` (Twilio credentials, API keys)

### When working on database/models
- **Models:** `app/models.py:8-46` (ConversationSession)
- **Database setup:** `app/db.py:5-18`

### When working on Salesforce integration
- **Stub implementation:** `app/salesforce.py:5-36`

### When working on tests
- **SMS tests:** `tests/test_twilio_sms.py`
- **Voice tests:** `tests/test_twilio_voice.py`
- **Test fixtures:** `tests/conftest.py`

## Common Development Tasks

### 1. Starting the Development Server

```bash
# Activate venv and run server
source .venv/bin/activate
uv run uvicorn app.main:app --reload --port 8000
```

**What this does:** Starts FastAPI on port 8000 with auto-reload on code changes.

### 2. Setting up ngrok for Twilio Webhooks

```bash
# Start ngrok tunnel
ngrok http 8000
```

**What this does:** Creates public HTTPS URL that forwards to localhost:8000.

**Next steps:**
1. Copy the ngrok URL (e.g., `https://abc123.ngrok.io`)
2. Configure Twilio webhooks:
   - SMS webhook: `POST {NGROK_URL}/twilio/sms`
   - Voice webhook: `POST {NGROK_URL}/twilio/voice`

### 3. Configuring Twilio Webhooks

Use Twilio Console or CLI:

```bash
# Using Twilio CLI (if installed)
twilio phone-numbers:update +16198530829 \
  --sms-url="https://YOUR-NGROK-URL.ngrok.io/twilio/sms" \
  --voice-url="https://YOUR-NGROK-URL.ngrok.io/twilio/voice"
```

**Manual configuration:**
1. Go to Twilio Console → Phone Numbers → Manage → Active Numbers
2. Click on +16198530829
3. Under "Messaging":
   - Configure webhook: `POST https://YOUR-NGROK-URL.ngrok.io/twilio/sms`
4. Under "Voice & Fax":
   - Configure webhook: `POST https://YOUR-NGROK-URL.ngrok.io/twilio/voice`
5. Save

### 4. Testing SMS Flow Locally

```bash
# Use the demo chatbot
python3 demo_chatbot.py

# Or send test SMS via Twilio (using demo in real mode)
python3 demo_chatbot.py --mode real --user-phone-number +15551234567
```

### 5. Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_twilio_sms.py

# With verbose output
uv run pytest -v

# With coverage
uv run pytest --cov=app
```

### 6. Viewing/Querying the Database

```bash
# Open SQLite CLI
sqlite3 nps_ivr.db

# Useful queries:
SELECT * FROM conversation_sessions ORDER BY created_at DESC LIMIT 10;
SELECT channel, status, COUNT(*) FROM conversation_sessions GROUP BY channel, status;
SELECT * FROM conversation_sessions WHERE status = 'open';
```

### 7. Checking Logs

```bash
# FastAPI logs appear in terminal where uvicorn is running
# ngrok logs
cat ngrok.log

# Or use ngrok web interface at http://localhost:4040
```

## Code Patterns to Follow

### Adding a New Required Field

1. Update `app/models.py:23-32` (REQUIRED_FIELDS list)
2. Update `app/models.py:34-43` (FIELD_PRETTY mapping)
3. Update `app/llm.py:16-25` (DEFAULT_QUESTIONS)
4. Update LLM system prompt in `app/llm.py:47-58` if needed
5. Update Salesforce mapping in `app/salesforce.py:19-30`

**Example:**
```python
# models.py
REQUIRED_FIELDS = [
    "first_name",
    # ... existing fields ...
    "new_field",  # Add here
]

FIELD_PRETTY = {
    # ... existing mappings ...
    "new_field": "New Field Label",
}

# llm.py
DEFAULT_QUESTIONS = {
    # ... existing questions ...
    "new_field": "What is your new field value?",
}
```

### Modifying LLM Behavior

Edit the system prompt in `app/llm.py:47-58`:

```python
sys = (
    "You are a lead intake assistant for National Powersports Auctions (NPA). "
    # Modify instructions here...
)
```

**Key considerations:**
- Keep instructions clear and specific
- Specify exact field names
- Include examples for ambiguous cases
- Maintain JSON response format requirement

### Adding a New Webhook Endpoint

Follow the pattern in `app/main.py`:

```python
@app.post("/twilio/new-endpoint", response_class=PlainTextResponse)
async def new_endpoint(request: Request):
    form = dict(await request.form())
    # Process form data
    # Return TwiML response
    return PlainTextResponse(str(response), media_type="application/xml")
```

### Session State Management

Sessions are automatically managed by `get_or_create_session()` in `app/main.py:29-41`.

**State structure:**
```python
session.state = {
    "first_name": "John",
    "last_name": "Doe",
    # ... other fields as collected
}
```

**Checking completion:**
```python
from app.models import missing_fields

miss = missing_fields(session.state)
done = len(miss) == 0
```

## Environment Variables

**Required:**
- `OPENAI_API_KEY` - OpenAI API key for LLM
- `TWILIO_SID` - Twilio Account SID
- `TWILIO_AUTH_TOKEN` - Twilio Auth Token
- `TWILIO_PHONE_NUMBER` - Twilio phone number

**Optional:**
- `OPENAI_MODEL` (default: gpt-4o-mini)
- `DATABASE_URL` (default: sqlite:///./nps_ivr.db)
- `SALESFORCE_BASE_URL` - For Salesforce integration
- `SALESFORCE_API_TOKEN` - For Salesforce integration

**Example `.env`:**
```
TWILIO_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+16198530829
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
```

## Debugging Tips

### SMS Webhook Not Responding

1. Check ngrok is running: `curl http://localhost:4040/api/tunnels`
2. Check FastAPI is running: `curl http://localhost:8000/health`
3. Check Twilio webhook configuration
4. View requests in ngrok dashboard: http://localhost:4040
5. Check FastAPI logs for errors

### Voice Call Issues

1. Verify TwiML syntax in response
2. Check `<Gather>` configuration in `app/main.py:95-98`
3. Ensure `/twilio/voice/collect` endpoint is accessible
4. Review Twilio Debugger in Console

### LLM Not Extracting Fields

1. Check OpenAI API key is set
2. Review system prompt in `app/llm.py:47-58`
3. Check OpenAI API response in logs
4. Verify JSON response format
5. Test with demo_chatbot.py to isolate issue

### Database Issues

1. Check database file exists: `ls -l nps_ivr.db`
2. Verify schema: `sqlite3 nps_ivr.db ".schema"`
3. Check for locked database (close other connections)
4. Reset database: `rm nps_ivr.db` (then restart app to recreate)

## Quick Command Reference

```bash
# Environment
source .venv/bin/activate
pyenv local 3.11.13

# Dependencies
uv pip install .[test]
uv pip install -r requirements.txt

# Development
uv run uvicorn app.main:app --reload --port 8000
ngrok http 8000

# Testing
uv run pytest
uv run pytest -v
uv run pytest --cov=app

# Database
sqlite3 nps_ivr.db
sqlite3 nps_ivr.db "SELECT * FROM conversation_sessions;"

# Demo
python3 demo_chatbot.py
python3 demo_chatbot.py --mode real --user-phone-number +1234567890

# Git
git status
git add .
git commit -m "message"
git push

# Logs
tail -f ngrok.log
# FastAPI logs in uvicorn terminal
```

## Architecture Quick Reference

### Request Flow (SMS)
```
User SMS → Twilio → ngrok → FastAPI /twilio/sms
  ↓
get_or_create_session (by SmsSid)
  ↓
process_turn (extract fields via OpenAI)
  ↓
Update session.state in DB
  ↓
If done: create_lead → Salesforce
  ↓
TwiML <Message> response → Twilio → User SMS
```

### Request Flow (Voice)
```
User Call → Twilio → ngrok → FastAPI /twilio/voice
  ↓
get_or_create_session (by CallSid)
  ↓
TwiML <Gather> with welcome message
  ↓
User speaks/DTMF → Twilio → /twilio/voice/collect
  ↓
process_turn (extract fields via OpenAI)
  ↓
If incomplete: <Gather> with next question
If complete: create_lead, <Say> goodbye, <Hangup>
```

## Important Behaviors & Quirks

### 1. Address Field
The system asks for "address" but **only wants the STATE**, not a full address. This is intentional per `app/llm.py:50-51`:
```python
"IMPORTANT: For the 'address' field, we only need the STATE of residence."
```

### 2. Vehicle Year Normalization
The system automatically extracts 4-digit years from text using regex in `app/llm.py:27-42`.

### 3. Context-Aware Field Inference
The LLM uses conversation context to infer which field the user is answering. See `app/llm.py:51-53`:
```python
"IMPORTANT: When the user provides a short direct answer (like just 'Smith' or 'John'),
use the conversation context to infer which field they're answering."
```

### 4. Session Identification
- SMS: Session identified by `SmsSid` (message ID)
- Voice: Session identified by `CallSid` (call ID)

### 5. Lead Submission
Leads are submitted to Salesforce **only once** when `done=True` and `session.status != "closed"`. The session is then marked as "closed" to prevent duplicate submissions.

### 6. Voice Gather Timeouts
- `timeout=6` seconds for no input
- `speechTimeout="auto"` for speech end detection
- See `app/main.py:95`

## Modifying for New Phone Number

When you get a new Twilio phone number:

1. Update `.env`:
   ```
   TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
   ```

2. Configure webhooks on new number (see "Configuring Twilio Webhooks" above)

3. Restart FastAPI server to pick up new environment variable

4. Test with demo_chatbot.py or direct SMS/call

## Production Deployment Checklist

- [ ] Add Twilio signature verification (uncomment/enable in webhooks)
- [ ] Restrict CORS to specific origins
- [ ] Switch to PostgreSQL from SQLite
- [ ] Add rate limiting
- [ ] Configure proper logging (not just stdout)
- [ ] Set up monitoring/alerts
- [ ] Add authentication to endpoints
- [ ] Configure proper error handling and user-friendly messages
- [ ] Set up proper Salesforce integration (not stub)
- [ ] Use environment variable manager (not .env file)
- [ ] Enable HTTPS (not just via ngrok)
- [ ] Set up proper CI/CD pipeline
- [ ] Add admin dashboard for lead management

## Useful Twilio Testing Numbers

Twilio provides magic test numbers (when using test credentials):
- +15005550006 - Valid number that can receive SMS/calls
- Full list: https://www.twilio.com/docs/iam/test-credentials

## When Things Go Wrong

### "No module named 'app'"
- Make sure you're in project root: `/Users/tifox/timfox456/nps_ivr`
- Activate venv: `source .venv/bin/activate`

### "Module 'openai' has no attribute 'X'"
- Check OpenAI library version: `pip show openai`
- Required: openai>=1.51.0

### "Database is locked"
- Close all SQLite connections
- Restart FastAPI server

### "ngrok tunnel not found"
- Check ngrok is running: `ps aux | grep ngrok`
- Restart ngrok: `ngrok http 8000`

### Twilio webhooks timing out
- Check ngrok tunnel is up
- Check FastAPI is responding: `curl localhost:8000/health`
- Increase timeout if using slow OpenAI responses

## Contact & Resources

- **Twilio Console:** https://console.twilio.com
- **OpenAI API Status:** https://status.openai.com
- **FastAPI Docs:** https://fastapi.tiangolo.com
- **Twilio Docs:** https://www.twilio.com/docs
- **ngrok Dashboard:** http://localhost:4040 (when running)

## Project Maintenance

### Updating Dependencies
```bash
# Update all dependencies
uv pip install --upgrade -r requirements.txt

# Update specific package
uv pip install --upgrade openai
```

### Database Migrations (Future)
When Alembic is configured:
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

### Viewing Recent Conversations
```sql
-- In sqlite3 nps_ivr.db
SELECT
    id,
    channel,
    from_number,
    status,
    json_extract(state, '$.first_name') as first_name,
    json_extract(state, '$.last_name') as last_name,
    created_at
FROM conversation_sessions
ORDER BY created_at DESC
LIMIT 10;
```

---

**Last Updated:** 2025-10-09
**Project Version:** 0.1.0
**Python:** 3.11.13
**Active Phone:** +16198530829
