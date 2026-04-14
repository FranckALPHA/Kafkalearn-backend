"""
models/user_feedback.py
=======================
Feedback explicite de l'utilisateur — ce qu'il dit directement au système.
C'est de l'or pur : l'utilisateur est le meilleur signal sur lui-même.
"""
from sqlalchemy import (
    Column, Integer, Float, String, Text, ForeignKey,
    CheckConstraint, Index, TIMESTAMP, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class UserFeedback(Base, TimestampMixin):
    """
    Feedback explicite sur un contenu, une session, ou le système en général.
    Utilisé pour mettre à jour immédiatement le profil comportemental.
    """
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Quoi ?
    feedback_type = Column(String(30), nullable=False)
    # "content_format" : "je préfère les schémas aux textes"
    # "content_difficulty" : "c'est trop facile/difficile"
    # "session_quality" : "cette session m'a aidé / pas aidé"
    # "coach_message" : "ton message était motivant / décourageant"
    # "system_suggestion" : "cette recommandation était pertinente / pas"

    # Évaluation
    rating = Column(Float, nullable=True)  # 1-5
    comment = Column(Text, nullable=True)  # libre

    # Contexte
    related_entity_type = Column(String(30), nullable=True)  # "quiz", "fiche", "exercise", "search", "coach"
    related_entity_id = Column(Integer, nullable=True)
    matiere = Column(String(100), nullable=True)
    concept = Column(String(200), nullable=True)

    # Résultat : est-ce que le feedback a été pris en compte ?
    action_taken = Column(String(50), nullable=True)
    # "updated_content_preference"
    # "adjusted_difficulty"
    # "noted_for_coach"
    # "ignored_insufficient_data"

    user = relationship("User")

    __table_args__ = (
        CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="chk_feedback_rating_range"),
        Index("idx_feedback_user", "user_id", "created_at"),
        Index("idx_feedback_type", "feedback_type"),
    )

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "feedback_type": self.feedback_type,
            "rating": self.rating,
            "comment": self.comment,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "matiere": self.matiere,
            "concept": self.concept,
            "action_taken": self.action_taken,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserFeedback(user={self.user_id}, type={self.feedback_type}, rating={self.rating})>"
