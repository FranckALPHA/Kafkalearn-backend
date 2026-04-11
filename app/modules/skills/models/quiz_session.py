"""
models/quiz_session.py
======================
Table quiz_sessions — Sessions de quiz interactives.
"""
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, TIMESTAMP,
    CheckConstraint, Index, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class QuizSession(Base, TimestampMixin):
    __tablename__ = "quiz_sessions"

    # ─── Identifiants ────────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    chat_session_id = Column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=True, index=True
    )

    # ─── Métadonnées quiz ────────────────────────────────────────
    titre = Column(String(255), nullable=False)
    matiere = Column(String(100), nullable=True, index=True)
    niveau = Column(String(50), nullable=True)
    notion = Column(String(200), nullable=True)
    type_quiz = Column(String(20), default="qcm")  # qcm|qro|vrai_faux|mixte
    difficulte = Column(String(20), default="moyen")  # facile|moyen|difficile

    # ─── Données quiz ────────────────────────────────────────────
    questions = Column(JSONB, nullable=False, default=list)  # structure complète du quiz
    nb_questions = Column(Integer, default=0)

    # ─── Réponses utilisateur ────────────────────────────────────
    reponses_utilisateur = Column(JSONB, nullable=True)  # {question_id: reponse}
    nb_bonnes_reponses = Column(Integer, default=0)
    nb_mauvaises_reponses = Column(Integer, default=0)
    score_percent = Column(Float, nullable=True)  # 0-100

    # ─── Timing ──────────────────────────────────────────────────
    started_at = Column(TIMESTAMP, nullable=False)
    submitted_at = Column(TIMESTAMP, nullable=True, index=True)
    duree_secondes = Column(Integer, nullable=True)

    # ─── Lacunes détectées ───────────────────────────────────────
    lacunes_detectees = Column(JSONB, nullable=True)  # [{notion, score, ...}]

    # ─── Relations ───────────────────────────────────────────────
    user = relationship("User")
    chat_session = relationship("ChatSession", back_populates="quiz_sessions")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_user_matiere", "user_id", "matiere"),
        Index("idx_user_started", "user_id", "started_at"),
    )

    # ─── Méthodes utilitaires ────────────────────────────────────
    @property
    def is_submitted(self) -> bool:
        return self.submitted_at is not None

    @property
    def is_passing(self) -> bool:
        return (self.score_percent or 0) >= 50

    def calculate_score(self):
        """Calcule le score en pourcentage."""
        total = self.nb_bonnes_reponses + self.nb_mauvaises_reponses
        if total == 0:
            self.score_percent = 0
        else:
            self.score_percent = round((self.nb_bonnes_reponses / total) * 100, 1)

    def serialize(self) -> dict:
        return {
            "id": str(self.id),
            "titre": self.titre,
            "matiere": self.matiere,
            "niveau": self.niveau,
            "type_quiz": self.type_quiz,
            "difficulte": self.difficulte,
            "nb_questions": self.nb_questions,
            "nb_bonnes_reponses": self.nb_bonnes_reponses,
            "score_percent": self.score_percent,
            "is_passing": self.is_passing,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "duree_secondes": self.duree_secondes,
            "lacunes_detectees": self.lacunes_detectees,
        }

    def __repr__(self) -> str:
        return f"<QuizSession(id={self.id}, user_id={self.user_id}, titre='{self.titre}')>"
