"""
models/wisdom_user_interaction.py
=================================
Modèle WisdomUserInteraction — Interactions utilisateur avec les conseils.
"""
from app.core.database import Base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DATE,
    CheckConstraint,
    Index,
    ForeignKey,
    UniqueConstraint,
    TIMESTAMP,
    func
)


class WisdomUserInteraction(Base):
    """Trace les interactions d'un utilisateur avec un conseil de sagesse."""

    __tablename__ = "wisdom_user_interactions"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    wisdom_id = Column(
        Integer,
        ForeignKey("wisdom_tips.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    vue = Column(Boolean, default=True, nullable=False)
    note = Column(
        Integer,
        CheckConstraint("note BETWEEN 1 AND 5", name="chk_wisdom_interaction_note"),
        nullable=True
    )
    partage = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "wisdom_id", name="idx_user_wisdom_unique"),
        Index("idx_wisdom_note", "wisdom_id", "note"),
    )

    # Relationships
    user = relationship("User")
    tip = relationship("WisdomTip")

    def __repr__(self) -> str:
        return f"<WisdomUserInteraction user={self.user_id} wisdom={self.wisdom_id}>"
