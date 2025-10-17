from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Web config
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Twilio
    twilio_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Database
    database_url: str = "sqlite:///./nps_ivr.db"

    # NPA API (formerly Salesforce placeholder)
    npa_api_base_url: str = "https://npadsapi.dev.npauctions.com"
    npa_api_username: Optional[str] = None
    npa_api_password: Optional[str] = None
    npa_lead_source: str = "IVR"  # Default lead source for IVR calls/SMS

settings = Settings()