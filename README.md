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

## Docker Deployment

### Quick Start with Docker

The application can be deployed using Docker for a containerized, production-ready setup.

**Prerequisites:**
- Docker Engine 20.10+
- Docker Compose 2.0+
- `.env` file with required credentials

**1. Configure Environment Variables**

Ensure your `.env` file contains:
```bash
# Twilio Configuration
TWILIO_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1234567890

# OpenAI Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini

# NPA API Configuration
NPA_API_USERNAME=your_username
NPA_API_PASSWORD=your_password
NPA_LEAD_SOURCE=IVR
```

**2. Build and Start the Container**

```bash
# Build and start in detached mode
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

**3. Verify Deployment**

```bash
# Test health endpoint
curl http://localhost:8000/health

# Should return: {"ok":true}
```

### Using Makefile Commands

The project includes a Makefile for common operations:

```bash
make build      # Build Docker image
make up         # Start container
make down       # Stop and remove container
make restart    # Restart container
make rebuild    # Rebuild and restart
make logs-f     # Follow logs in real-time
make health     # Check health endpoint
make status     # Show container status
make backup     # Backup SQLite database
make shell      # Open shell in container
make db-shell   # Open SQLite shell
```

### Data Persistence

The SQLite database is stored in `./data/nps_ivr.db` and persists across container restarts.

**Backup database:**
```bash
make backup
# or manually:
cp ./data/nps_ivr.db ./data/nps_ivr.db.backup.$(date +%Y%m%d_%H%M%S)
```

### Port Configuration

By default, the container exposes port 8000. To change the host port, edit `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Maps host port 8001 to container port 8000
```

### Container Management

```bash
# View logs (last 100 lines)
docker compose logs --tail=100 nps-ivr

# View real-time logs
docker compose logs -f nps-ivr

# Restart after code changes
docker compose up -d --build

# Stop container (data persists)
docker compose stop

# Remove container and volumes (WARNING: deletes database!)
docker compose down -v
```

### Production Deployment

For production deployment:

1. **Use a reverse proxy** (Nginx/Caddy) with SSL/TLS
2. **Set proper resource limits** in `docker-compose.yml`
3. **Configure log aggregation** (optional)
4. **Set up health monitoring**
5. **Use Docker secrets** for sensitive environment variables

See [DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md) for detailed production setup instructions, including:
- Reverse proxy configuration
- SSL/HTTPS setup
- Resource tuning
- Monitoring and troubleshooting
- Security best practices

## Local tunneling
Use `ngrok` (or similar) to expose FastAPI:
```bash
ngrok http 8000
```
Copy the public URL.

## Configure Twilio Webhooks
- SMS: set Messaging webhook to `POST {PUBLIC_URL}/twilio/sms`
- Voice: set Voice webhook to `POST {PUBLIC_URL}/twilio/voice`

## Environment Variables

**Required:**
- `OPENAI_API_KEY`: OpenAI API key for conversational AI
- `TWILIO_SID`: Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Twilio Auth Token
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number (e.g., +16198530829)
- `NPA_API_USERNAME`: NPA API username for lead submission
- `NPA_API_PASSWORD`: NPA API password

**Optional:**
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-4o-mini)
- `DATABASE_URL`: Database connection string (default: sqlite:///./nps_ivr.db)
- `USE_POSTGRES`: Set to "true" to use PostgreSQL instead of SQLite (default: false)
- `NPA_LEAD_SOURCE`: Lead source identifier (default: IVR)
- `LOG_LEVEL`: Logging level (default: INFO)

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
