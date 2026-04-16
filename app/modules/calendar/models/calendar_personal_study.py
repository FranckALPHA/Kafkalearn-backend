"""
models/calendar_personal_study.py
=================================
Entité CalendarPersonalStudy — entrées d'étude personnelle.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    TIME,
    CheckConstraint,
    Index,
    ForeignKey,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class CalendarPersonalStudy(Base):
    __tablename__ = "calendar_personal_study"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(100), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(TIME, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    priority = Column(String(10), default="normal")
    is_active = Column(Boolean, default=True, index=True)

    __table_args__ = (
        CheckConstraint(
            "day_of_week BETWEEN 0 AND 6",
            name="ck_day_of_week_range"
        ),
        CheckConstraint(
            "duration_minutes BETWEEN 5 AND 240",
            name="ck_duration_minutes_range"
        ),
        CheckConstraint(
            "priority IN ('low', 'normal', 'high')",
            name="ck_priority_valid"
        ),
    )

    user = relationship("User")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc)

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "subject": self.subject,
            "day_of_week": self.day_of_week,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "duration_minutes": self.duration_minutes,
            "priority": self.priority,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
