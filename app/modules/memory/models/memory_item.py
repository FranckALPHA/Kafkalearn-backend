"""
models/memory_item.py
=====================
Entité MemoryItem — éléments individuels (flashcards, QCM, etc.).
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class MemoryItem(Base):
    __tablename__ = "memory_items"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(
        Integer,
        ForeignKey("memory_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    item_type = Column(String(15), nullable=False)

    # ─── Contenu ─────────────────────────────────────────────────
    content_json = Column(JSONB, nullable=False)
    fingerprint = Column(String(64), nullable=False, index=True)

    # ─── Statistiques ────────────────────────────────────────────
    taux_reussite = Column(Float, default=0.0)
    nb_tentatives = Column(Integer, default=0)
    difficulte_percue = Column(Float, default=0.5)

    # ─── Relations ───────────────────────────────────────────────
    section = relationship("MemorySection", back_populates="items")
    attempts = relationship(
        "MemoryItemAttempt", back_populates="item", cascade="all, delete-orphan"
    )

    # ─── Contraintes & Index ─────────────────────────────────────
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('flashcard','qcm','cloze','short_answer')",
            name="chk_item_type"
        ),
        CheckConstraint("taux_reussite BETWEEN 0 AND 1", name="chk_taux_reussite_range"),
        CheckConstraint("nb_tentatives >= 0", name="chk_nb_tentatives_gte_0"),
        CheckConstraint("difficulte_percue BETWEEN 0 AND 1", name="chk_difficulte_percue_range"),
        UniqueConstraint("section_id", "fingerprint", name="idx_fingerprint_unique"),
        Index("idx_difficulty", "difficulte_percue", "taux_reussite"),
    )

    # ─── Méthodes ────────────────────────────────────────────────
    def get_content_for_language(self, langue: str = "fr") -> dict:
        """Retourne le contenu adapté à la langue demandée.
        Supporte deux formats :
        - Bilingue : {"fr": {"question":..., "answer":...}, "en": {...}}
        - Legacy : {"question":..., "answer":..., "translations": {"en":...}}
        """
        content = dict(self.content_json) if self.content_json else {}

        # Format bilingue (nouveau)
        if langue in content and isinstance(content[langue], dict):
            return content[langue]

        # Fallback sur le français si la langue demandée n'existe pas
        if "fr" in content and isinstance(content["fr"], dict):
            return content["fr"]

        # Format legacy avec translations
        translations = content.get("translations", {})
        if langue in translations:
            content.update(translations[langue])

        return content

    def serialize_for_review(
        self, langue: str = "fr", reveal_answer: bool = False
    ) -> dict:
        """Sérialisation pour la revue / l'affichage."""
        content = self.get_content_for_language(langue)
        result = {
            "id": self.id,
            "section_id": self.section_id,
            "item_type": self.item_type,
            "content": {
                "question": content.get("question", ""),
                "options": content.get("options"),
                "difficulty": content.get("difficulty", "medium"),
            },
            "taux_reussite": self.taux_reussite,
            "nb_tentatives": self.nb_tentatives,
            "difficulte_percue": self.difficulte_percue,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if reveal_answer:
            result["answer"] = content.get("answer")
            result["explanation"] = content.get("explanation")
        return result

    def __repr__(self) -> str:
        return f"<MemoryItem(id={self.id}, type='{self.item_type}', section={self.section_id})>"
