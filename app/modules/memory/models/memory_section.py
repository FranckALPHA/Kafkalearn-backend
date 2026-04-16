"""
models/memory_section.py
========================
Entité MemorySection — sections mémoires extraites des documents.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    ForeignKey,
    CheckConstraint,
    Index,
    TIMESTAMP,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class MemorySection(Base):
    __tablename__ = "memory_sections"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        Integer, ForeignKey("pedagogical_assets.id", ondelete="SET NULL"), nullable=True
    )

    # ─── Contenu ─────────────────────────────────────────────────
    section_title = Column(String(255), nullable=False)
    section_order = Column(Integer, nullable=False)
    section_summary = Column(Text, nullable=True)

    # ─── Statistiques ────────────────────────────────────────────
    nb_items = Column(Integer, default=0)
    difficulte_moyenne = Column(Float, nullable=True)
    nb_utilisateurs_actifs = Column(Integer, default=0)

    # ─── Pipeline IA ─────────────────────────────────────────────
    generation_status = Column(String(20), default="pending", nullable=False)
    generation_error = Column(Text, nullable=True)
    generated_at = Column(TIMESTAMP, nullable=True)

    # ─── Relations ───────────────────────────────────────────────
    document = relationship("Document")
    items = relationship(
        "MemoryItem", back_populates="section", cascade="all, delete-orphan"
    )
    user_progress = relationship(
        "UserSectionProgress", back_populates="section", cascade="all, delete-orphan"
    )

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("section_order >= 0", name="chk_section_order_gte_0"),
        CheckConstraint("nb_items >= 0", name="chk_nb_items_gte_0"),
        CheckConstraint(
            "difficulte_moyenne BETWEEN 0 AND 1", name="chk_difficulte_moyenne_range"
        ),
        CheckConstraint(
            "nb_utilisateurs_actifs >= 0", name="chk_nb_utilisateurs_actifs_gte_0"
        ),
        CheckConstraint(
            "generation_status IN ('pending','generating','complete','partial','failed')",
            name="chk_generation_status",
        ),
        Index("idx_doc_order", "document_id", "section_order"),
        Index("idx_generation", "generation_status", "generated_at"),
        Index(
            "idx_memory_section_popularity",
            "nb_utilisateurs_actifs",
            "difficulte_moyenne",
        ),
    )

    # ─── Propriétés ──────────────────────────────────────────────
    @property
    def is_ready_for_review(self) -> bool:
        """La section est-elle prête pour la revue ?"""
        return self.generation_status in ("complete", "partial")

    # ─── Sérialisation ───────────────────────────────────────────
    def serialize_list_item(self, user_progress=None) -> dict:
        """Sérialisation légère pour les listes."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "section_title": self.section_title,
            "section_order": self.section_order,
            "section_summary": self.section_summary,
            "nb_items": self.nb_items,
            "difficulte_moyenne": self.difficulte_moyenne,
            "nb_utilisateurs_actifs": self.nb_utilisateurs_actifs,
            "generation_status": self.generation_status,
            "is_ready_for_review": self.is_ready_for_review,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "user_progress": user_progress.serialize_progress()
            if user_progress
            else None,
        }

    def __repr__(self) -> str:
        return f"<MemorySection(id={self.id}, title='{self.section_title}', order={self.section_order})>"
