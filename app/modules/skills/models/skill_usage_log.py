"""
models/skill_usage_log.py
=========================
Table skill_usage_logs — Journal d'utilisation des skills.
"""
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    CheckConstraint,
    Index,
    ForeignKey,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class SkillUsageLog(Base):
    __tablename__ = "skill_usage_logs"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identifiants ────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    chat_message_id = Column(Integer, nullable=True, index=True)  # lien optionnel

    # ─── Skill exécuté ───────────────────────────────────────────
    skill_type = Column(
        String(20),
        CheckConstraint(
            "skill_type IN ('fiche','quiz','solver','tuteur','corrige','epreuve','visualisation')"
        ),
        nullable=False,
        index=True,
    )

    # ─── Contexte pédagogique ────────────────────────────────────
    matiere = Column(String(100), nullable=True, index=True)
    niveau = Column(String(50), nullable=True)
    notion = Column(String(200), nullable=True)

    # ─── Prompt et params ────────────────────────────────────────
    prompt_utilise = Column(Text, nullable=True)
    params_utilises = Column(JSONB, nullable=True)

    # ─── Résultat ────────────────────────────────────────────────
    succes = Column(Boolean, default=True, nullable=False)
    erreur_code = Column(String(50), nullable=True)
    latence_ms = Column(Integer, nullable=True)
    tokens_utilises = Column(Integer, nullable=True)
    llm_provider = Column(String(20), nullable=True)
    rag_chunks_utilises = Column(Integer, default=0)

    # ─── Quota ───────────────────────────────────────────────────
    quota_consomme = Column(Boolean, default=True, nullable=False)

    # ─── Relations ───────────────────────────────────────────────
    user = relationship("User")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_user_skill_created", "user_id", "skill_type", "created_at"),
        Index("idx_matiere_skill", "matiere", "skill_type"),
    )

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "skill_type": self.skill_type,
            "matiere": self.matiere,
            "niveau": self.niveau,
            "notion": self.notion,
            "succes": self.succes,
            "erreur_code": self.erreur_code,
            "latence_ms": self.latence_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<SkillUsageLog(id={self.id}, user_id={self.user_id}, skill='{self.skill_type}')>"
