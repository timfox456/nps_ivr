# NPA IVR/SMS Lead Intake (FastAPI)

FastAPI + Twilio SMS/Voice intake that collects lead info for National Powersports Auctions (NPA), using OpenAI to extract fields from free-form user input. Stores session state in SQLite and posts a lead to Salesforce (stub).

## Features
- Twilio SMS webhook: conversational intake via text
- Twilio Voice webhook: speech + DTMF via <Gather>
- OpenAI-assisted field extraction and next-question prompting
- SQLite session storage
- Salesforce lead creation placeholder

## Python Version (pyenv)
This repo targets Python 3.11.13 via pyenv.
- Install: `pyenv install 3.11.13`
- Set local version (already set): `.python-version`

## Package/Env Manager (uv)
We use uv to manage dependencies and run tasks from `pyproject.toml`.
- Create/activate env: `uv venv && source .venv/bin/activate` (or let uv manage automatically)
- Install deps: `uv pip install -r requirements.txt` or `uv pip install .[test]`
- Run dev server: `uv run uvicorn app.main:app --reload`
- Run tests: `uv run pytest`

## Quick Start
```bash
pyenv install -s 3.11.13
pyenv local 3.11.13
uv pip install .[test]
export OPENAI_API_KEY=sk-...
uv run uvicorn app.main:app --reload
```

## Local tunneling
Use `ngrok` (or similar) to expose FastAPI:
```bash
ngrok http 8000
```
Copy the public URL.

## Configure Twilio Webhooks
- SMS: set Messaging webhook to `POST {PUBLIC_URL}/twilio/sms`
- Voice: set Voice webhook to `POST {PUBLIC_URL}/twilio/voice`

## Environment
- `OPENAI_API_KEY`: OpenAI API key
- `OPENAI_MODEL` (optional, default gpt-4o-mini)
- `DATABASE_URL` (optional, default sqlite:///./nps_ivr.db)
- `SALESFORCE_BASE_URL` and `SALESFORCE_API_TOKEN` to enable lead posting

## Notes
- The Salesforce client is a stub; add your real endpoint and mapping.
- For production, validate Twilio signatures and add auth/allowlists on webhooks.
