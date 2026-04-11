"""
models/chat_session.py
======================
Table chat_sessions — Sessions de conversation skills.
"""
import uuid
from sqlalchemy import (
    Column, String, Integer, Boolean, SMALLINT, TIMESTAMP,
    CheckConstraint, Index, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    # ─── Identifiants ────────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # ─── Métadonnées session ─────────────────────────────────────
    titre = Column(String(255), default="Nouvelle session", nullable=False)
    skill_predominant = Column(String(20), nullable=True)
    matiere = Column(String(100), nullable=True, index=True)

    # ─── Compteurs dénormalisés ──────────────────────────────────
    nb_messages = Column(Integer, default=0, CheckConstraint("nb_messages >= 0"))
    nb_generations_reussies = Column(Integer, default=0, CheckConstraint("nb_generations_reussies >= 0"))
    nb_generations_echouees = Column(Integer, default=0, CheckConstraint("nb_generations_echouees >= 0"))

    # ─── Satisfaction utilisateur ────────────────────────────────
    note_utilisateur = Column(
        SMALLINT, CheckConstraint("note_utilisateur BETWEEN 1 AND 5"), nullable=True
    )

    # ─── Gestion affichage ───────────────────────────────────────
    is_archived = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False, index=True)

    # ─── Aperçu liste ────────────────────────────────────────────
    last_message_preview = Column(String(200), nullable=True)

    # ─── Relations ───────────────────────────────────────────────
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )
    quiz_sessions = relationship("QuizSession", back_populates="chat_session", lazy="dynamic")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_user_updated", "user_id", "updated_at"),
        Index("idx_user_pinned", "user_id", "is_pinned", "updated_at"),
    )

    # ─── Méthodes utilitaires ────────────────────────────────────
    def add_message_preview(self, content: str, max_length: int = 200):
        self.last_message_preview = content[:max_length].strip()

    def increment_generation(self, success: bool):
        if success:
            self.nb_generations_reussies += 1
        else:
            self.nb_generations_echouees += 1

    def serialize_list_item(self) -> dict:
        return {
            "id": str(self.id),
            "titre": self.titre,
            "skill_predominant": self.skill_predominant,
            "matiere": self.matiere,
            "nb_messages": self.nb_messages,
            "note_utilisateur": self.note_utilisateur,
            "is_pinned": self.is_pinned,
            "last_message_preview": self.last_message_preview,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, titre='{self.titre}')>"
