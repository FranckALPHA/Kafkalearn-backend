"""
models/chat_message.py
======================
Table chat_messages — Messages individuels dans une session chat.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Index, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # Metadata skill
    skill_utilise = Column(String(50), nullable=True)
    output_type = Column(String(20), nullable=True)
    file_url = Column(String(255), nullable=True)
    json_data = Column(JSONB, nullable=True)
    matiere = Column(String(100), nullable=True)
    niveau = Column(String(50), nullable=True)
    latence_ms = Column(Integer, nullable=True)
    tokens_utilises = Column(Integer, nullable=True)
    llm_provider = Column(String(50), nullable=True)

    # Feedback
    feedback = Column(Integer, nullable=True)  # 1, 0, -1
    feedback_at = Column(TIMESTAMP, nullable=True)

    # Tracking
    erreur_code = Column(String(50), nullable=True)
    idempotency_key = Column(String(100), nullable=True, index=True)

    session = relationship("ChatSession", back_populates="messages")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc)

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "session_id": str(self.session_id),
            "role": self.role,
            "content": self.content,
            "skill_utilise": self.skill_utilise,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def serialize_for_chat(self) -> dict:
        """Format spécifique pour l'API chat."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "skill_utilise": self.skill_utilise,
            "output_type": self.output_type,
            "file_url": self.file_url,
            "json_data": self.json_data,
            "matiere": self.matiere,
            "niveau": self.niveau,
            "latence_ms": self.latence_ms,
            "erreur_code": self.erreur_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
