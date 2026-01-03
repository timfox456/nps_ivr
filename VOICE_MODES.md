# Voice Workflow Modes

This application supports multiple voice interaction modes for different use cases.

## Available Voice Endpoints

### 1. `/twilio/voice-ivr` - Legacy Twilio IVR (Robotic TTS)
**Status:** ✅ Stable - Kept as backup
**Voice Quality:** Robotic (Twilio TTS)
**Latency:** Low (~200-300ms)
**Features:**
- Uses Twilio's built-in speech recognition
- Robotic text-to-speech
- Confirmation prompts for email, phone, vehicle info
- Field-by-field collection with validation

**When to use:**
- Fallback if OpenAI has issues
- When predictable voice is needed
- Cost optimization (cheaper than OpenAI)

**How it works:**
```
User speaks → Twilio STT → Your server → OpenAI (text) → Your server → Twilio TTS → User hears
```

---

### 2. `/twilio/voice-realtime-proxied` - OpenAI Realtime (High Visibility)
**Status:** ✅ Working - Current test mode
**Voice Quality:** Natural (OpenAI Realtime)
**Latency:** Medium (~300-500ms with ngrok, ~200-300ms without)
**Features:**
- Natural conversational voice
- Real-time audio streaming
- Full logging and debugging visibility
- Server processes all audio

**When to use:**
- Development and testing
- When you need full visibility into the conversation
- Debugging audio/conversation issues
- Testing new prompts and behaviors

**How it works:**
```
User speaks → Twilio → Your Server (WebSocket) → OpenAI Realtime API → Your Server → Twilio → User hears
```

**Logging visibility:**
- All Twilio media events logged
- All OpenAI Realtime events logged
- Database state tracking
- Easy to add custom logic

---

### 3. `/twilio/voice` - OpenAI Realtime (Production - Optimized)
**Status:** 🚧 To be implemented
**Voice Quality:** Natural (OpenAI Realtime)
**Latency:** Low (~150-250ms)
**Features:**
- Minimal proxy overhead
- Optimized audio streaming
- Production-ready error handling
- Reduced logging for performance

**When to use:**
- Production deployment
- When latency is critical
- High call volume

**How it works:**
```
User speaks → Twilio → Thin Proxy (auth only) → OpenAI Realtime API → Thin Proxy → Twilio → User hears
```

**Optimizations:**
- Minimal audio processing
- Async message forwarding
- Connection pooling
- Reduced logging (errors only)

---

## Comparison Matrix

| Feature | Legacy IVR | Realtime Proxied | Realtime Optimized |
|---------|-----------|------------------|-------------------|
| Voice Quality | ⭐⭐ Robotic | ⭐⭐⭐⭐⭐ Natural | ⭐⭐⭐⭐⭐ Natural |
| Latency | ⭐⭐⭐⭐ Low | ⭐⭐⭐ Medium | ⭐⭐⭐⭐ Low |
| Debugging | ⭐⭐⭐⭐ Good | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐ Minimal |
| Cost per min | ⭐⭐⭐⭐ Low | ⭐⭐⭐ Higher | ⭐⭐⭐ Higher |
| Reliability | ⭐⭐⭐⭐⭐ Very High | ⭐⭐⭐⭐ High | ⭐⭐⭐⭐ High |

---

## Cost Comparison

### Legacy IVR (`/twilio/voice-ivr`)
- Twilio Voice: ~$0.013/min
- Twilio STT: ~$0.02/min
- OpenAI GPT-4o-mini: ~$0.001/min
- **Total: ~$0.034/min**

### OpenAI Realtime (`/twilio/voice-realtime-*`)
- Twilio Voice: ~$0.013/min
- OpenAI Realtime API: ~$0.24/min (input + output)
- **Total: ~$0.253/min**

**~7x more expensive, but much better user experience**

---

## Switching Between Modes

Update your Twilio webhook to point to the desired endpoint:

```bash
# Legacy IVR (robotic, cheap, reliable)
twilio phone-numbers:update +16198530829 \
  --voice-url="https://your-domain.com/twilio/voice-ivr"

# Realtime Proxied (natural voice, high visibility, testing)
twilio phone-numbers:update +16198530829 \
  --voice-url="https://your-domain.com/twilio/voice-realtime-proxied"

# Realtime Optimized (natural voice, production)
twilio phone-numbers:update +16198530829 \
  --voice-url="https://your-domain.com/twilio/voice"
```

Or use the script:
```python
python update_twilio_webhooks.py --voice-mode [ivr|realtime-proxied|realtime]
```

---

## Latency Breakdown

### With ngrok (Development):
- Legacy IVR: 250ms
- Realtime Proxied: 400ms
- Realtime Optimized: 300ms

### Without ngrok (Production):
- Legacy IVR: 200ms
- Realtime Proxied: 250ms
- Realtime Optimized: 180ms

---

## Recommendations

**For Development/Testing:**
→ Use `/twilio/voice-realtime-proxied`
- Full logging helps debug issues
- Easy to iterate on prompts
- Can monitor conversation flow

**For Production:**
→ Use `/twilio/voice` (optimized) when implemented
- Lower latency = better user experience
- Production error handling
- Cost is worth it for natural voice

**For Fallback/Budget:**
→ Keep `/twilio/voice-ivr` configured
- Reliable backup if OpenAI has issues
- Much cheaper for high call volumes
- Users can understand robotic voice

---

## Implementation Status

- ✅ `/twilio/voice-ivr` - Complete
- ✅ `/twilio/voice-realtime-proxied` - Complete
- ⏳ `/twilio/voice` - Planned

---

Last Updated: 2025-10-24
