"""
models/wisdom_tip.py
====================
Modèle WisdomTip — Conseils de sagesse quotidiens.
"""
from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, TIMESTAMP, DATE,
    CheckConstraint, Index, ForeignKey, func
)


class WisdomTip(Base, TimestampMixin):
    """Conseil de sagesse quotidien généré ou administré."""

    __tablename__ = "wisdom_tips"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tip_date = Column(DATE, nullable=False, unique=True, index=True)
    content_json = Column(JSONB, nullable=False)
    category = Column(
        String(20),
        CheckConstraint(
            "category IN ('vie','etudes','philosophie','strategie','challenge','vigilance','humour')",
            name="chk_wisdom_tip_category"
        ),
        nullable=False
    )
    source = Column(
        String(10),
        CheckConstraint("source IN ('llm','static','admin')", name="chk_wisdom_tip_source"),
        nullable=False,
        default="llm"
    )
    llm_provider = Column(String(20), nullable=True)
    nb_vues = Column(
        Integer,
        CheckConstraint("nb_vues >= 0", name="chk_wisdom_tip_nb_vues"),
        default=0
    )
    nb_partages = Column(
        Integer,
        CheckConstraint("nb_partages >= 0", name="chk_wisdom_tip_nb_partages"),
        default=0
    )
    rating_moyen = Column(
        Float,
        CheckConstraint("rating_moyen BETWEEN 1 AND 5", name="chk_wisdom_tip_rating_moyen"),
        nullable=True
    )
    nb_notes = Column(
        Integer,
        CheckConstraint("nb_notes >= 0", name="chk_wisdom_tip_nb_notes"),
        default=0
    )
    latence_generation_ms = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_wisdom_tip_date", "tip_date"),
        Index("idx_wisdom_tip_category_source", "category", "source"),
    )

    # Relationships
    interactions = relationship(
        "WisdomUserInteraction",
        back_populates="tip",
        cascade="all, delete-orphan"
    )

    def get_text(self, langue: str = "fr") -> dict:
        """Extrait le texte et l'auteur pour la langue donnée."""
        content = self.content_json.get(langue, {})
        return {
            "text": content.get("text", ""),
            "author": content.get("author", ""),
        }

    def serialize(self, langue: str = "fr") -> dict:
        """Sérialise le conseil en dictionnaire."""
        return {
            "id": self.id,
            "tip_date": str(self.tip_date),
            "content": self.get_text(langue),
            "category": self.category,
            "source": self.source,
            "llm_provider": self.llm_provider,
            "nb_vues": self.nb_vues,
            "nb_partages": self.nb_partages,
            "rating_moyen": self.rating_moyen,
            "nb_notes": self.nb_notes,
            "latence_generation_ms": self.latence_generation_ms,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<WisdomTip id={self.id} date={self.tip_date} category={self.category}>"
