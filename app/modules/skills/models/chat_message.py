"""
models/chat_message.py
======================
Table chat_messages — Messages individuels dans une session.
"""
from sqlalchemy import (
    Column, String, Text, Integer, SMALLINT, TIMESTAMP,
    CheckConstraint, Index, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"

    # ─── Identifiants ────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ─── Contenu message ─────────────────────────────────────────
    role = Column(
        String(10),
        CheckConstraint("role IN ('user','assistant','system')"),
        nullable=False,
    )
    content = Column(Text, nullable=False)

    # ─── Métadonnées génération (assistant uniquement) ───────────
    skill_utilise = Column(String(20), nullable=True)
    output_type = Column(
        String(10),
        CheckConstraint("output_type IN ('text','pdf','json','png')"),
        nullable=True,
    )
    file_url = Column(String(500), nullable=True)
    json_data = Column(JSONB, nullable=True)

    # ─── Contexte pédagogique ────────────────────────────────────
    matiere = Column(String(100), nullable=True, index=True)
    niveau = Column(String(50), nullable=True)

    # ─── Métriques performance ───────────────────────────────────
    latence_ms = Column(Integer, nullable=True)
    tokens_utilises = Column(Integer, nullable=True)
    llm_provider = Column(String(20), nullable=True)

    # ─── Feedback utilisateur ────────────────────────────────────
    feedback = Column(
        SMALLINT, CheckConstraint("feedback IN (-1, 1)"), nullable=True
    )
    feedback_at = Column(TIMESTAMP, nullable=True)

    # ─── Gestion erreurs ─────────────────────────────────────────
    erreur_code = Column(String(50), nullable=True)

    # ─── Idempotency ─────────────────────────────────────────────
    idempotency_key = Column(String(100), unique=True, nullable=True, index=True)

    # ─── Relations ───────────────────────────────────────────────
    session = relationship("ChatSession", back_populates="messages")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_session_created", "session_id", "created_at"),
        Index("idx_feedback_skill", "skill_utilise", "feedback"),
    )

    # ─── Méthodes utilitaires ────────────────────────────────────
    def is_assistant_message(self) -> bool:
        return self.role == "assistant"

    def has_generated_content(self) -> bool:
        return self.is_assistant_message() and (self.file_url or self.json_data or self.content)

    def serialize_for_chat(self) -> dict:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "skill_utilise": self.skill_utilise,
            "output_type": self.output_type,
            "file_url": self.file_url,
            "json_data": self.json_data if self.output_type == "json" else None,
            "feedback": self.feedback,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role='{self.role}', session_id={self.session_id})>"
