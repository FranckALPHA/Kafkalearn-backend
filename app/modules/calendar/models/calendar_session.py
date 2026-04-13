from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, ForeignKey, Integer, String, Text, Float, Boolean, TIMESTAMP, CheckConstraint, Index, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class CalendarSession(TimestampMixin, Base):
    __tablename__ = "calendar_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String(100), nullable=False, index=True)
    titre = Column(String(255), nullable=True)
    planned_start = Column(TIMESTAMP, nullable=False)
    planned_end = Column(TIMESTAMP, nullable=False)
    planned_duration_minutes = Column(Integer, nullable=False)
    status = Column(String(15), default="planned", index=True)
    actual_start = Column(TIMESTAMP, nullable=True)
    actual_end = Column(TIMESTAMP, nullable=True)
    accumulated_seconds = Column(Integer, default=0)
    last_ping = Column(TIMESTAMP, nullable=True)
    nb_pauses = Column(Integer, default=0)
    concentration_ratio = Column(Float, nullable=True)
    score_session = Column(Float, nullable=True)
    humeur_debut = Column(String(15), nullable=True)
    humeur_fin = Column(String(15), nullable=True)
    note_session = Column(Text, nullable=True)
    ressource_principale_id = Column(Integer, nullable=True)
    ressource_principale_type = Column(String(20), nullable=True)
    is_ai_generated = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "planned_duration_minutes BETWEEN 5 AND 480",
            name="ck_planned_duration_range"
        ),
        CheckConstraint(
            "status IN ('planned', 'active', 'paused', 'completed', 'failed', 'skipped', 'cancelled')",
            name="ck_status_valid"
        ),
        CheckConstraint(
            "accumulated_seconds >= 0",
            name="ck_accumulated_seconds_non_neg"
        ),
        CheckConstraint(
            "nb_pauses >= 0",
            name="ck_nb_pauses_non_neg"
        ),
        CheckConstraint(
            "concentration_ratio IS NULL OR (concentration_ratio BETWEEN 0 AND 1)",
            name="ck_concentration_ratio_range"
        ),
        CheckConstraint(
            "score_session IS NULL OR (score_session BETWEEN 0 AND 100)",
            name="ck_score_session_range"
        ),
        CheckConstraint(
            "humeur_debut IS NULL OR humeur_debut IN ('motive', 'neutre', 'fatigue', 'stresse')",
            name="ck_humeur_debut_valid"
        ),
        CheckConstraint(
            "humeur_fin IS NULL OR humeur_fin IN ('satisfait', 'neutre', 'epuise', 'frustre')",
            name="ck_humeur_fin_valid"
        ),
        CheckConstraint(
            "ressource_principale_type IS NULL OR ressource_principale_type IN ('document', 'asset', 'memory_section')",
            name="ck_ressource_type_valid"
        ),
        Index("idx_user_planned", "user_id", "planned_start"),
        Index("idx_user_status", "user_id", "status"),
        Index("idx_user_subject_status", "user_id", "subject", "status"),
        Index("idx_due_reminders", "status", "planned_start"),
    )

    user = relationship("User")
    ping_log = relationship(
        "SessionPingLog",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan"
    )

    @property
    def is_active_or_planned(self) -> bool:
        return self.status in ("planned", "active", "paused")

    @property
    def is_overdue(self) -> bool:
        if self.planned_end is None:
            return False
        now = datetime.now(timezone.utc) if self.planned_end.tzinfo else datetime.now()
        return self.planned_end < now

    @property
    def effective_duration_minutes(self) -> float:
        return self.accumulated_seconds / 60

    def calculate_concentration_ratio(self) -> float:
        if self.planned_duration_minutes <= 0:
            return 0.0
        effective = self.effective_duration_minutes
        ratio = effective / self.planned_duration_minutes
        return min(max(ratio, 0.0), 1.0)

    def serialize_for_list(self) -> dict:
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "subject": self.subject,
            "titre": self.titre,
            "planned_start": self.planned_start.isoformat() if self.planned_start else None,
            "planned_end": self.planned_end.isoformat() if self.planned_end else None,
            "planned_duration_minutes": self.planned_duration_minutes,
            "status": self.status,
            "actual_start": self.actual_start.isoformat() if self.actual_start else None,
            "actual_end": self.actual_end.isoformat() if self.actual_end else None,
            "accumulated_seconds": self.accumulated_seconds,
            "concentration_ratio": self.concentration_ratio,
            "score_session": self.score_session,
            "humeur_debut": self.humeur_debut,
            "humeur_fin": self.humeur_fin,
            "is_ai_generated": self.is_ai_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def serialize_detail(self) -> dict:
        data = self.serialize_for_list()
        data.update({
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "nb_pauses": self.nb_pauses,
            "note_session": self.note_session,
            "ressource_principale_id": self.ressource_principale_id,
            "ressource_principale_type": self.ressource_principale_type,
            "effective_duration_minutes": self.effective_duration_minutes,
            "is_active_or_planned": self.is_active_or_planned,
            "is_overdue": self.is_overdue,
        })
        return data
