"""
models/analysis_feedback.py
===========================
Modèle SQLAlchemy pour les retours utilisateurs sur les analyses de documents.
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, TIMESTAMP,
    CheckConstraint, Index, UniqueConstraint, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class AnalysisFeedback(Base, TimestampMixin):
    __tablename__ = "analysis_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(
        Integer,
        ForeignKey("document_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    est_utile = Column(Boolean, nullable=False)
    section_problematique = Column(String(20), nullable=True)
    commentaire = Column(String(500), nullable=True)

    # Relationships
    analysis = relationship("DocumentAnalysis", back_populates="feedbacks")

    __table_args__ = (
        CheckConstraint(
            "section_problematique IN ('key_points','concepts','tips','summary','methodologie')",
            name="ck_analysis_feedback_section",
        ),
        UniqueConstraint("analysis_id", "user_id", name="idx_analysis_user_unique"),
        Index("idx_useful", "est_utile", "analysis_id"),
    )

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "analysis_id": self.analysis_id,
            "user_id": str(self.user_id),
            "est_utile": self.est_utile,
            "section_problematique": self.section_problematique,
            "commentaire": self.commentaire,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
