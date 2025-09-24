from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Web config
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Twilio
    twilio_auth_token: Optional[str] = None  # Optional signature validation

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Database
    database_url: str = "sqlite:///./nps_ivr.db"

    # Salesforce placeholder
    salesforce_base_url: Optional[str] = None
    salesforce_api_token: Optional[str] = None

settings = Settings()