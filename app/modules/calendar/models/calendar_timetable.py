from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, TIME, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class CalendarTimetable(TimestampMixin, Base):
    __tablename__ = "calendar_timetable"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    subject = Column(String(100), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(TIME, nullable=False)
    end_time = Column(TIME, nullable=False)
    is_active = Column(Boolean, default=True, index=True)

    __table_args__ = (
        CheckConstraint(
            "day_of_week BETWEEN 0 AND 6",
            name="ck_day_of_week_range"
        ),
        UniqueConstraint(
            "user_id", "day_of_week", "start_time", "end_time",
            name="uq_user_day_time"
        ),
        Index("idx_user_day", "user_id", "day_of_week"),
    )

    user = relationship("User", back_populates="timetable_entries")

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "subject": self.subject,
            "day_of_week": self.day_of_week,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
