from datetime import datetime, timedelta

from sqlalchemy import Column, Integer, TIMESTAMP, CheckConstraint, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class SessionPingLog(TimestampMixin, Base):
    __tablename__ = "session_ping_logs"

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

    def add_ping(self, current_time: datetime, delta_seconds: int) -> None:
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
