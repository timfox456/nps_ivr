from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Integer, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel: Mapped[str] = mapped_column(String(16), index=True)  # 'sms' | 'voice'
    session_key: Mapped[str] = mapped_column(String(64), index=True)  # SmsSid or CallSid or From
    from_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    state: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # collected fields
    last_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_prompt_field: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FailedLead(Base):
    __tablename__ = "failed_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lead_data: Mapped[Dict[str, Any]] = mapped_column(JSON)  # Complete lead JSON
    error_message: Mapped[str] = mapped_column(Text)  # Error details
    channel: Mapped[str] = mapped_column(String(16), index=True)  # 'sms' | 'voice'
    session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Link to conversation_sessions.id
    retry_count: Mapped[int] = mapped_column(Integer, default=0)  # Number of retry attempts
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Last retry timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Integer, default=0)  # 0=pending, 1=successfully submitted

REQUIRED_FIELDS = [
    "full_name",
    "zip_code",
    "phone",
    "email",
    "vehicle_make",
    "vehicle_model",
    "vehicle_year",
]

FIELD_PRETTY = {
    "full_name": "Full Name",
    "zip_code": "ZIP Code",
    "phone": "Phone",
    "email": "Email",
    "vehicle_make": "Make of Vehicle",
    "vehicle_model": "Model of Vehicle",
    "vehicle_year": "Year of Vehicle",
}

def missing_fields(state: Dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_FIELDS if not (state.get(f) and str(state.get(f)).strip())]
