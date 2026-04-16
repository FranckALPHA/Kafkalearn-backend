"""
models/notification_preference.py
==================================
User notification preferences and quiet hours configuration.
"""
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Time,
    Index,
    ForeignKey,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quiz_dispo = Column(Boolean, default=True, nullable=False)
    memory_review = Column(Boolean, default=True, nullable=False)
    session_rappel = Column(Boolean, default=True, nullable=False)
    streaks = Column(Boolean, default=True, nullable=False)
    payment = Column(Boolean, default=True, nullable=False)
    lacunes = Column(Boolean, default=True, nullable=False)
    marketing = Column(Boolean, default=False, nullable=False)
    heure_silencieuse_debut = Column(Time, nullable=True, default=lambda: _parse_time("22:00"))
    heure_silencieuse_fin = Column(Time, nullable=True, default=lambda: _parse_time("07:00"))

    __table_args__ = (
        Index("idx_pref_user", "user_id"),
    )

    user = relationship("User")

    def is_quiet_hour(self, check_time=None):
        """Check if the given time falls within quiet hours."""
        from datetime import datetime, time as dt_time
        if check_time is None:
            check_time = datetime.now().time()
        if not isinstance(check_time, dt_time):
            check_time = check_time.time() if hasattr(check_time, 'time') else check_time

        debut = self.heure_silencieuse_debut
        fin = self.heure_silencieuse_fin
        if debut is None or fin is None:
            return False

        # Handle midnight crossing (e.g., 22:00 -> 07:00)
        if debut <= fin:
            return debut <= check_time <= fin
        else:
            return check_time >= debut or check_time <= fin

    def serialize(self):
        """Return dict representation for API responses."""
        return {
            "quiz_dispo": self.quiz_dispo,
            "memory_review": self.memory_review,
            "session_rappel": self.session_rappel,
            "streaks": self.streaks,
            "payment": self.payment,
            "lacunes": self.lacunes,
            "marketing": self.marketing,
            "heure_silencieuse_debut": self.heure_silencieuse_debut.isoformat() if self.heure_silencieuse_debut else None,
            "heure_silencieuse_fin": self.heure_silencieuse_fin.isoformat() if self.heure_silencieuse_fin else None,
        }


def _parse_time(t_str):
    """Parse 'HH:MM' string to time object."""
    from datetime import time as dt_time
    parts = t_str.split(":")
    return dt_time(int(parts[0]), int(parts[1]))
