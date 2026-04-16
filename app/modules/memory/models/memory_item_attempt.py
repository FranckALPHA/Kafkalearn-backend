"""
models/memory_item_attempt.py
=============================
Historique des tentatives sur les éléments mémoire.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class MemoryItemAttempt(Base):
    __tablename__ = "memory_item_attempts"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    item_id = Column(
        Integer,
        ForeignKey("memory_items.id"),
        nullable=False,
        index=True
    )
    section_id = Column(
        Integer,
        ForeignKey("memory_sections.id"),
        nullable=False
    )

    # ─── Tentative ───────────────────────────────────────────────
    reponse_donnee = Column(Text, nullable=True)
    est_correct = Column(Boolean, nullable=False)
    qualite_reponse = Column(Integer, nullable=True)
    duree_secondes = Column(Integer, nullable=True)

    # ─── Relations ───────────────────────────────────────────────
    item = relationship("MemoryItem", back_populates="attempts")

    # ─── Index ───────────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("qualite_reponse BETWEEN 0 AND 5", name="chk_qualite_reponse_range"),
        Index("idx_item_attempts", "item_id", "created_at"),
        Index("idx_user_section_attempts", "user_id", "section_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<MemoryItemAttempt(id={self.id}, user={self.user_id}, "
            f"item={self.item_id}, correct={self.est_correct})>"
        )
