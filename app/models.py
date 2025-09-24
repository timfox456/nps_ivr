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

REQUIRED_FIELDS = [
    "first_name",
    "last_name",
    "address",
    "phone",
    "email",
    "vehicle_make",
    "vehicle_model",
    "vehicle_year",
]

FIELD_PRETTY = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "address": "Address",
    "phone": "Phone",
    "email": "Email",
    "vehicle_make": "Make of Vehicle",
    "vehicle_model": "Model of Vehicle",
    "vehicle_year": "Year of Vehicle",
}

def missing_fields(state: Dict[str, Any]) -> list[str]:
    return [f for f in REQUIRED_FIELDS if not (state.get(f) and str(state.get(f)).strip())]
