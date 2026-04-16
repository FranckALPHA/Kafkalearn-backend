from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, Integer, TIMESTAMP, CheckConstraint, Index, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class SessionPingLog(Base):
    __tablename__ = "session_ping_logs"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("calendar_sessions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    nb_pings = Column(Integer, default=0)
    premier_ping = Column(TIMESTAMP, nullable=True)
    dernier_ping = Column(TIMESTAMP, nullable=True)
    gaps_detectes = Column(JSONB, default=list, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "nb_pings >= 0",
            name="ck_nb_pings_non_neg"
        ),
    )

    session = relationship("CalendarSession", back_populates="ping_log")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc)

    def add_ping(self, current_time: datetime, delta_seconds: int) -> None:
        if self.nb_pings is None:
            self.nb_pings = 0
        self.nb_pings += 1

        if self.premier_ping is None:
            self.premier_ping = current_time

        if self.dernier_ping is not None:
            gap = (current_time - self.dernier_ping).total_seconds()
            if gap > 120:
                if self.gaps_detectes is None:
                    self.gaps_detectes = []
                self.gaps_detectes.append({
                    "from": self.dernier_ping.isoformat(),
                    "to": current_time.isoformat(),
                    "gap_seconds": gap,
                })

        self.dernier_ping = current_time
