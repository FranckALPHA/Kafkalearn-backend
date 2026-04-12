"""
models/document_analysis.py
===========================
Modèle SQLAlchemy pour l'analyse de documents (épreuves / leçons).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, TIMESTAMP,
    CheckConstraint, Index, UniqueConstraint, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class DocumentAnalysis(Base, TimestampMixin):
    __tablename__ = "document_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    langue = Column(String(5), nullable=False)
    document_hash = Column(String(64), nullable=False)
    analysis_type = Column(String(10), nullable=False)
    analysis_version = Column(String(10), default="v1", nullable=False)
    key_points = Column(JSONB, default=list, nullable=True)
    concepts = Column(JSONB, default=list, nullable=True)
    tips = Column(JSONB, default=list, nullable=True)
    summary = Column(Text, nullable=True)
    methodologie = Column(Text, nullable=True)
    difficulte_detail = Column(JSONB, nullable=True)
    notions_prerequis = Column(JSONB, default=list, nullable=True)
    llm_provider = Column(String(20), nullable=True)
    latence_ms = Column(Integer, nullable=True)
    nb_acces = Column(Integer, default=0)
    feedback_utile = Column(Integer, default=0)
    feedback_pas_utile = Column(Integer, default=0)
    analyzed_at = Column(TIMESTAMP, server_default=func.now(), nullable=False, index=True)
    refreshed_at = Column(TIMESTAMP, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="analyses")
    feedbacks = relationship(
        "AnalysisFeedback",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("langue IN ('fr', 'en')", name="ck_doc_analysis_langue"),
        CheckConstraint(
            "analysis_type IN ('epreuve', 'lecon')",
            name="ck_doc_analysis_type",
        ),
        CheckConstraint("nb_acces >= 0", name="ck_doc_analysis_nb_acces"),
        CheckConstraint("feedback_utile >= 0", name="ck_doc_analysis_feedback_utile"),
        CheckConstraint(
            "feedback_pas_utile >= 0",
            name="ck_doc_analysis_feedback_pas_utile",
        ),
        UniqueConstraint("document_id", "langue", name="idx_doc_lang_unique"),
        Index("idx_type_analyzed", "analysis_type", "analyzed_at"),
        Index("idx_feedback_ratio", "feedback_utile", "feedback_pas_utile"),
    )

    @property
    def taux_utilite(self) -> Optional[float]:
        total = self.feedback_utile + self.feedback_pas_utile
        if total == 0:
            return None
        return round(self.feedback_utile / total, 4)

    @property
    def is_outdated(self) -> bool:
        # Placeholder: implement versioning / staleness logic here
        return False

    def serialize(self, include_feedback: bool = False) -> dict:
        data = {
            "id": self.id,
            "document_id": self.document_id,
            "langue": self.langue,
            "document_hash": self.document_hash,
            "analysis_type": self.analysis_type,
            "analysis_version": self.analysis_version,
            "key_points": self.key_points,
            "concepts": self.concepts,
            "tips": self.tips,
            "summary": self.summary,
            "methodologie": self.methodologie,
            "difficulte_detail": self.difficulte_detail,
            "notions_prerequis": self.notions_prerequis,
            "llm_provider": self.llm_provider,
            "latence_ms": self.latence_ms,
            "nb_acces": self.nb_acces,
            "feedback_utile": self.feedback_utile,
            "feedback_pas_utile": self.feedback_pas_utile,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "refreshed_at": self.refreshed_at.isoformat() if self.refreshed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "taux_utilite": self.taux_utilite,
            "is_outdated": self.is_outdated,
        }
        if include_feedback:
            data["feedbacks"] = [f.serialize() for f in self.feedbacks]
        return data
