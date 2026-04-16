"""
models/user_section_progress.py
===============================
Suivi de progression des utilisateurs sur les sections mémoire.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserSectionProgress(Base):
    __tablename__ = "user_section_progress"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    section_id = Column(
        Integer,
        ForeignKey("memory_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # ─── Progression ─────────────────────────────────────────────
    is_completed = Column(Boolean, default=False, nullable=False)
    completed_items_count = Column(Integer, default=0)
    total_items_count = Column(Integer, default=0)
    current_item_index = Column(Integer, default=0)

    # ─── Scoring ─────────────────────────────────────────────────
    score_section = Column(Float, default=0.0)
    nb_erreurs = Column(Integer, default=0)
    nb_revisions = Column(Integer, default=0)

    # ─── Planification SM-2 ──────────────────────────────────────
    last_reviewed_at = Column(TIMESTAMP, nullable=True)
    next_review_at = Column(TIMESTAMP, nullable=True, index=True)
    easiness_factor = Column(Float, default=2.5)
    interval_jours = Column(Integer, default=1)

    # ─── Relations ───────────────────────────────────────────────
    user = relationship("User")
    section = relationship("MemorySection")

    # ─── Contraintes & Index ─────────────────────────────────────
    __table_args__ = (
        CheckConstraint("completed_items_count >= 0", name="chk_completed_items_gte_0"),
        CheckConstraint("total_items_count >= 0", name="chk_total_items_gte_0"),
        CheckConstraint("current_item_index >= 0", name="chk_current_item_index_gte_0"),
        CheckConstraint("score_section BETWEEN 0 AND 100", name="chk_score_section_range"),
        CheckConstraint("nb_erreurs >= 0", name="chk_nb_erreurs_gte_0"),
        CheckConstraint("nb_revisions >= 0", name="chk_nb_revisions_gte_0"),
        CheckConstraint("easiness_factor >= 1.3", name="chk_easiness_factor_gte_1_3"),
        CheckConstraint("interval_jours >= 1", name="chk_interval_jours_gte_1"),
        UniqueConstraint("user_id", "section_id", name="idx_user_section_unique"),
        Index("idx_due_reviews", "user_id", "next_review_at"),
    )

    # ─── Méthodes ────────────────────────────────────────────────
    def serialize_progress(self) -> dict:
        """Sérialisation complète de la progression."""
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "section_id": self.section_id,
            "is_completed": self.is_completed,
            "completed_items_count": self.completed_items_count,
            "total_items_count": self.total_items_count,
            "current_item_index": self.current_item_index,
            "score_section": self.score_section,
            "nb_erreurs": self.nb_erreurs,
            "nb_revisions": self.nb_revisions,
            "last_reviewed_at": self.last_reviewed_at.isoformat() if self.last_reviewed_at else None,
            "next_review_at": self.next_review_at.isoformat() if self.next_review_at else None,
            "easiness_factor": self.easiness_factor,
            "interval_jours": self.interval_jours,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_due_for_review(self, grace_hours: int = 24) -> bool:
        """Vérifie si la section est due pour une revue."""
        if self.next_review_at is None:
            return True
        now = datetime.now(timezone.utc)
        if self.next_review_at.tzinfo is None:
            self.next_review_at = self.next_review_at.replace(tzinfo=timezone.utc)
        grace = timedelta(hours=grace_hours)
        return now >= (self.next_review_at - grace)

    def __repr__(self) -> str:
        return (
            f"<UserSectionProgress(user={self.user_id}, section={self.section_id}, "
            f"score={self.score_section})>"
        )
