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

## Demo Chatbot CLI
A command-line interface is available to test the chatbot logic.

### Running the Demo
1.  **Activate the virtual environment:**
    ```bash
    source .venv/bin/activate
    ```

2.  **Run in simulation mode:**
    This mode prints the conversation to the console without sending real SMS messages.
    ```bash
    python3 demo_chatbot.py
    ```

3.  **Run in real mode:**
    This mode sends real SMS messages using your Twilio account. Ensure your `TWILIO_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER` are set as environment variables or in a `.env` file.
    ```bash
    python3 demo_chatbot.py --mode real --user-phone-number <your_phone_number>
    ```
    Replace `<your_phone_number>` with the destination phone number.

## Notes
- The Salesforce client is a stub; add your real endpoint and mapping.
- For production, validate Twilio signatures and add auth/allowlists on webhooks.
