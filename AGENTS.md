# NPA IVR/SMS Lead Intake System - Agent Documentation

## Project Overview

**Name:** NPA IVR/SMS Lead Intake System
**Purpose:** FastAPI + Twilio SMS/Voice intake system that collects lead information for National Powersports Auctions (NPA), using OpenAI to extract fields from free-form user input.

## Architecture

### Technology Stack
- **Backend Framework:** FastAPI 0.112.2
- **Server:** Uvicorn 0.30.6
- **Database:** SQLite (SQLAlchemy 2.0.35 ORM)
- **AI/LLM:** OpenAI API (gpt-4o-mini by default)
- **Telephony:** Twilio SDK 9.3.3 (SMS + Voice)
- **HTTP Client:** httpx 0.27.2
- **Python Version:** 3.11.13 (managed via pyenv)
- **Package Manager:** uv

### Core Components

#### 1. Application Entry (`app/main.py`)
- FastAPI application with CORS middleware
- Webhook endpoints for Twilio SMS and Voice
- Session management and lead processing orchestration

**Key Endpoints:**
- `POST /twilio/sms` - SMS webhook handler
- `POST /twilio/voice` - Voice call initial handler
- `POST /twilio/voice/collect` - Voice input collection handler
- `GET /health` - Health check endpoint

#### 2. Configuration (`app/config.py`)
- Pydantic Settings-based configuration
- Loads from `.env` file
- Configuration keys:
  - `TWILIO_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
  - `OPENAI_API_KEY`, `OPENAI_MODEL` (default: gpt-4o-mini)
  - `DATABASE_URL` (default: sqlite:///./nps_ivr.db)
  - `SALESFORCE_BASE_URL`, `SALESFORCE_API_TOKEN`

#### 3. Database Layer (`app/db.py` & `app/models.py`)
- SQLAlchemy with declarative base
- Single table: `ConversationSession`

**ConversationSession Schema:**
```python
- id: int (primary key)
- channel: str ('sms' | 'voice')
- session_key: str (SmsSid or CallSid)
- from_number: str (caller phone)
- to_number: str (Twilio phone)
- state: JSON (collected lead fields)
- last_prompt: text
- last_prompt_field: str
- status: str ('open' | 'closed')
- created_at: datetime
- updated_at: datetime
```

**Required Fields:**
```python
REQUIRED_FIELDS = [
    "first_name",
    "last_name",
    "address",        # Only STATE needed, not full address
    "phone",
    "email",
    "vehicle_make",
    "vehicle_model",
    "vehicle_year"
]
```

#### 4. LLM Processing (`app/llm.py`)
- OpenAI integration for conversational field extraction
- Context-aware question generation
- Field normalization (especially for vehicle_year)

**Key Functions:**
- `extract_and_prompt(user_text, state)` - Extracts fields from user input and generates next question
- `process_turn(user_text, state)` - Main conversation turn processor
- `normalize_fields(fields)` - Normalizes extracted fields (e.g., extracts 4-digit year)

**Important LLM Behavior:**
- Uses JSON response format for structured extraction
- Context-aware: infers which field user is answering based on conversation state
- For "address" field: only collects STATE, not full address
- Temperature: 0.7 for natural conversation variety

#### 5. Salesforce Integration (`app/salesforce.py`)
- Async lead creation via httpx
- Currently a placeholder/stub implementation
- Maps lead fields to Salesforce Lead object schema

#### 6. Twilio Utilities (`app/twilio_utils.py`)
- HMAC-SHA1 signature verification (for webhook security)
- Base64 encoded signature validation
- Optional use (not currently enforced in webhooks)

### Application Flow

#### SMS Flow
1. User sends SMS to Twilio number
2. Twilio POSTs to `/twilio/sms` with form data
3. System retrieves or creates session by SmsSid
4. `process_turn()` extracts fields from message and generates next question
5. State updated in database
6. If all fields collected → call `create_lead()` and close session
7. TwiML `<Message>` response sent back to user

#### Voice Flow
1. User calls Twilio number
2. Twilio POSTs to `/twilio/voice`
3. System creates session with CallSid
4. TwiML `<Gather>` returned with welcome message
5. User speaks/enters DTMF
6. Twilio POSTs to `/twilio/voice/collect` with SpeechResult/Digits
7. `process_turn()` processes input
8. If incomplete → return `<Gather>` with next question
9. If complete → create lead, say goodbye, `<Hangup>`

### Environment Setup

**Example .env Configuration:**
```
TWILIO_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+15551234567
```

### Testing

**Test Files:**
- `tests/test_health.py` - Health endpoint test
- `tests/test_llm_and_models.py` - LLM and model logic tests
- `tests/test_twilio_sms.py` - SMS webhook integration tests
- `tests/test_twilio_voice.py` - Voice webhook integration tests

**Run Tests:**
```bash
uv run pytest
```

### Demo CLI Tool

**File:** `demo_chatbot.py`

A command-line chatbot for testing the intake flow without Twilio.

**Modes:**
- `simulate` (default) - Prints to console only
- `real` - Sends actual SMS via Twilio

**Usage:**
```bash
# Simulate mode
python3 demo_chatbot.py

# Real SMS mode
python3 demo_chatbot.py --mode real --user-phone-number +15551234567
```

### Development Workflow

**Initial Setup:**
```bash
pyenv install 3.11.13
pyenv local 3.11.13
source .venv/bin/activate
uv pip install .[test]
```

**Run Development Server:**
```bash
uv run uvicorn app.main:app --reload
```

**Expose via ngrok:**
```bash
ngrok http 8000
```

**Configure Twilio Webhooks:**
- SMS: `POST {NGROK_URL}/twilio/sms`
- Voice: `POST {NGROK_URL}/twilio/voice`

### Database

**Location:** `nps_ivr.db` (SQLite file in project root)

**Initialization:** Auto-creates tables on FastAPI startup via `init_db()`

**Schema Migrations:** Alembic 1.13.2 installed but not currently configured

### Security Considerations

1. **Twilio Signature Verification:** Implemented in `twilio_utils.py` but NOT enforced
   - For production: Add signature validation to webhook endpoints

2. **Environment Secrets:**
   - Credentials stored in `.env` (not in git via `.gitignore`)
   - DO NOT commit `.env` file

3. **API Keys:**
   - OpenAI API key required via `OPENAI_API_KEY`
   - Twilio credentials required for real SMS/Voice

4. **CORS:** Currently allows all origins (`allow_origins=["*"]`) - restrict in production

### Known Issues & TODOs

1. Salesforce integration is a stub - needs real endpoint
2. Twilio signature verification not enforced
3. No rate limiting on webhooks
4. Database uses SQLite (consider PostgreSQL for production)
5. No authentication on endpoints
6. CORS policy too permissive
7. Address field collection asks for state only - may confuse users expecting full address

### File Structure

```
nps_ivr/
├── .env                    # Environment configuration (not in git)
├── .python-version         # Python 3.11.13
├── pyproject.toml          # uv/pip configuration
├── requirements.txt        # Python dependencies
├── uv.lock                 # uv lock file
├── nps_ivr.db             # SQLite database
├── README.md              # User-facing documentation
├── AGENTS.md              # This file
├── CLAUDE.md              # Claude-specific guide (to be created)
├── demo_chatbot.py        # CLI demo tool
├── app/
│   ├── __init__.py
│   ├── config.py          # Settings/configuration
│   ├── db.py              # Database setup
│   ├── models.py          # SQLAlchemy models
│   ├── main.py            # FastAPI app & webhook endpoints
│   ├── llm.py             # OpenAI integration
│   ├── salesforce.py      # Salesforce client (stub)
│   ├── twilio_utils.py    # Twilio signature verification
│   └── run.py             # Application runner
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_llm_and_models.py
    ├── test_twilio_sms.py
    └── test_twilio_voice.py
```

### Common Commands

```bash
# Start development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app

# Start ngrok tunnel
ngrok http 8000

# Demo chatbot (simulate mode)
python3 demo_chatbot.py

# Demo chatbot (real SMS)
python3 demo_chatbot.py --mode real --user-phone-number +15551234567
```

### API Integration Notes

**Twilio Webhook POST Parameters (SMS):**
- `From` - Sender phone number
- `To` - Recipient (Twilio) phone number
- `Body` - Message text
- `SmsSid` / `MessageSid` - Unique message identifier

**Twilio Webhook POST Parameters (Voice):**
- `CallSid` - Unique call identifier
- `From` - Caller phone number
- `To` - Recipient (Twilio) phone number
- `SpeechResult` - Transcribed speech (from Gather)
- `Digits` - DTMF digits entered (from Gather)

### Performance Considerations

- SQLite with `check_same_thread=False` for FastAPI async compatibility
- OpenAI calls are synchronous (could be async-optimized)
- Session lookup by indexed fields (channel, session_key)
- JSON state storage in SQLite (no separate tables for fields)

### Future Enhancements

1. Add proper Salesforce integration
2. Implement webhook signature verification
3. Add rate limiting and abuse protection
4. Support multiple languages
5. Add analytics/reporting dashboard
6. Implement conversation history export
7. Add admin panel for viewing/managing leads
8. Support file uploads (vehicle photos)
9. Add SMS/Voice recording storage
10. Implement proper logging and monitoring
