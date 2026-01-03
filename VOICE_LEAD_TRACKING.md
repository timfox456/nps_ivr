# Voice Lead Tracking Implementation

## Overview

Voice calls using the OpenAI Realtime API now have complete lead submission and tracking, matching the SMS implementation.

## How It Works

### 1. Call Flow
```
User calls → Twilio → /twilio/voice-realtime-proxied (POST)
  ↓
Returns TwiML with <Connect><Stream>
  ↓
WebSocket connection to /twilio/voice/stream
  ↓
Bidirectional audio streaming:
  - Twilio → OpenAI Realtime API (caller audio)
  - OpenAI → Twilio (AI response audio)
  ↓
Conversation happens in real-time
  ↓
AI says goodbye message
  ↓
Trigger lead extraction and submission
```

### 2. Lead Extraction Process

**Location:** `app/voice_openai.py:375-511` (`_extract_and_submit_lead` method)

When goodbye message is detected:

1. **Request Full Conversation**
   - Sends `conversation.list` to OpenAI Realtime API
   - Collects all messages with transcripts
   - Builds full conversation text

2. **Extract Structured Data**
   - Uses OpenAI Chat Completions API with JSON mode
   - Extracts: full_name, zip_code, phone, vehicle_year, vehicle_make, vehicle_model
   - Temperature=0.0 for consistency

3. **Validate Fields**
   - Checks for missing required fields
   - Logs warnings but still attempts submission

4. **Submit to NPA API**
   - Success → Save to `succeeded_leads` table
   - Failure → Save to `failed_leads` table
   - User experience not affected (already heard goodbye)

## Database Tracking

### Session Creation
**Location:** `app/voice_openai.py:143-165` (`_get_or_create_session` method)

- Creates `ConversationSession` with channel="voice"
- session_key = CallSid
- State updated with extracted lead data at end

### Failed Leads
**Location:** `app/voice_openai.py:486-507`

When NPA API fails:
```python
FailedLead(
    lead_data=extracted_data,
    error_message=str(exception),
    channel="voice",
    session_id=conversation_session_id
)
```

### Succeeded Leads
**Location:** `app/voice_openai.py:472-481`

When NPA API succeeds:
```python
SucceededLead(
    lead_data=extracted_data,
    channel="voice",
    session_id=conversation_session_id,
    npa_response=api_response
)
```

## Key Differences from SMS

### SMS (Text-based)
- Extracts fields in real-time as conversation progresses
- Uses structured prompts to LLM for each turn
- Validates and normalizes each field immediately
- Submits when all fields collected

### Voice (Audio-based)
- Collects entire conversation first (no real-time extraction)
- Extracts all fields at once from full transcript
- Validation happens after conversation completes
- Submits after goodbye message

### Why Different?

**OpenAI Realtime API Limitations:**
- Conversation is handled entirely by OpenAI's voice agent
- No ability to intercept/modify conversation mid-stream
- Can only request conversation data after it's complete
- Voice-to-text transcription only available at end

**Benefits of This Approach:**
- Natural, uninterrupted conversation flow
- User doesn't experience delays
- Same end result: lead data captured and submitted

## Testing

### Check if Voice Tracking Works:

```bash
# Make a test voice call to your Twilio number
# Complete the conversation

# Check failed leads
python manage_failed_leads.py list

# Check succeeded leads
python view_succeeded_leads.py

# Check logs
journalctl -u nps-ivr --since "5 minutes ago" | grep -i "lead"
```

### Expected Log Output:

```
=== GOODBYE MESSAGE DETECTED - CALL COMPLETE ===
=== EXTRACTING LEAD DATA FROM CONVERSATION ===
=== CONVERSATION TEXT:
assistant: Thank you for calling Power Sport Buyers...
user: John Doe
assistant: What is your ZIP code?
user: 30093
...
=== EXTRACTED LEAD DATA: {'full_name': 'John Doe', 'zip_code': '30093', ...} ===
=== LEAD SUBMITTED SUCCESSFULLY ===
(or)
=== LEAD SUBMISSION FAILED: NPA API error: Unauthorized ===
```

## Troubleshooting

### No lead saved after call

**Check 1: Did conversation complete?**
```bash
journalctl -u nps-ivr --since "10 minutes ago" | grep "GOODBYE MESSAGE"
```
If not found: Conversation didn't reach completion (caller hung up early)

**Check 2: Was extraction attempted?**
```bash
journalctl -u nps-ivr --since "10 minutes ago" | grep "EXTRACTING LEAD"
```
If not found: Goodbye message not detected or exception occurred

**Check 3: Was conversation transcript retrieved?**
```bash
journalctl -u nps-ivr --since "10 minutes ago" | grep "CONVERSATION TEXT"
```
If not found: OpenAI didn't return conversation data

**Check 4: Were fields extracted?**
```bash
journalctl -u nps-ivr --since "10 minutes ago" | grep "EXTRACTED LEAD DATA"
```
Review what was extracted vs what's expected

### Extraction is incomplete

The extraction uses OpenAI Chat Completions to parse the transcript. If fields are missing:

1. **Check conversation transcript in logs** - Was the field actually discussed?
2. **Review extraction prompt** - Located at `app/voice_openai.py:422-433`
3. **Check for typos in conversation** - Voice transcription may misunderstand

### Failed lead not saved

Check for exceptions:
```bash
journalctl -u nps-ivr --since "10 minutes ago" | grep "ERROR IN LEAD EXTRACTION"
```

This indicates an exception in the extraction/submission logic itself.

## Costs

### Additional Cost per Call

Voice calls now use **two** OpenAI API calls:

1. **Realtime API** - Main voice conversation (existing cost)
2. **Chat Completions API** - Lead data extraction (new cost)

**Extraction Cost:**
- Model: gpt-4o-mini (configurable in .env)
- ~500-2000 tokens per extraction (depends on conversation length)
- Cost: ~$0.001-$0.004 per extraction
- Negligible compared to Realtime API cost (~$0.24-0.48 per minute)

## Configuration

### Environment Variables

**Required (existing):**
- `OPENAI_API_KEY` - API key for both Realtime and Chat Completions
- `TWILIO_SID`, `TWILIO_AUTH_TOKEN` - Twilio credentials
- `NPA_API_USERNAME`, `NPA_API_PASSWORD` - NPA API credentials

**Optional:**
- `OPENAI_MODEL` - Model for extraction (default: gpt-4o-mini)

### System Instructions

The voice agent's instructions are at `app/voice_openai.py:36-91` (SYSTEM_INSTRUCTIONS).

These control:
- What fields to collect
- How to confirm information
- ZIP code validation rules (5 digits, no AK/HI)
- When to say goodbye

## Maintenance

### If OpenAI Realtime API Changes

The conversation extraction depends on:
- `conversation.list` event type
- Message structure with `role`, `content`, `transcript` fields

If OpenAI changes these, update `_extract_and_submit_lead` method.

### If Required Fields Change

Update in three places:
1. `SYSTEM_INSTRUCTIONS` - Tell voice agent what to collect
2. `app/models.py:REQUIRED_FIELDS` - Validation logic
3. Extraction prompt at `app/voice_openai.py:422-433` - What to extract

## Related Files

- `app/voice_openai.py` - Main voice implementation
  - Line 375-511: Lead extraction and submission
  - Line 328-358: Goodbye detection and trigger
  - Line 143-165: Session management
- `app/models.py` - Database models (FailedLead, SucceededLead)
- `app/salesforce.py` - NPA API integration (create_lead function)
- `manage_failed_leads.py` - Failed lead management utility
- `view_succeeded_leads.py` - Succeeded lead viewer

## Future Enhancements

### 1. Real-time Field Tracking
- Parse conversation incrementally as it progresses
- Show field collection progress in dashboard
- Early detection of missing/invalid fields

### 2. Conversation Quality Metrics
- Track conversation length
- Identify fields that required multiple attempts
- Measure confirmation accuracy

### 3. Smart Retry Logic
- If extraction fails, retry with modified prompt
- Use multiple extraction attempts with voting
- Fallback to manual review queue

### 4. Conversation Recording
- Store full audio for quality assurance
- Link recordings to lead records
- Enable playback in admin dashboard

---

**Last Updated:** 2025-01-16
**Version:** 1.0
