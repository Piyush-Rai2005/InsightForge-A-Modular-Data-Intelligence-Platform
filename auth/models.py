"""
ORM models — User accounts and AnalysisSession history.
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("AnalysisSession", back_populates="user", cascade="all, delete-orphan")


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    report_json = Column(Text, default="{}")       # cached report payload
    dashboard_json = Column(Text, default="{}")     # cached dashboard payload
    chat_history = Column(Text, default="[]")       # JSON array of messages
    schedule_frequency = Column(String, default=None)

    user = relationship("User", back_populates="sessions")
