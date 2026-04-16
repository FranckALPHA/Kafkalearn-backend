"""
models/user_learning_profile.py
===============================
Profil cognitif de l'apprenant.
Les lacunes/forces/scores sont maintenant gérés par concept_graph (graphe cognitif).
Ce modèle conserve les données non relationnelles (historique, préférences, metadata).
"""
from sqlalchemy import Column, Integer, TIMESTAMP, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserLearningProfile(Base):
    __tablename__ = "user_learning_profiles"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True,
        nullable=False, index=True
    )

    # ─── Données non relationnelles (conservées) ──────────────────
    historique_recherches = Column(JSONB, default=list)  # FIFO 100
    interets = Column(JSONB, default=list)
    matieres_frequentes = Column(JSONB, default=dict)  # {matiere: count}
    heures_actives = Column(JSONB, default=dict)  # {heure: count}
    jours_actifs = Column(JSONB, default=dict)  # {jour: count}

    last_wisdom_id = Column(Integer, nullable=True)
    dernier_rapport_at = Column(TIMESTAMP, nullable=True)

    # Relation
    user = relationship("User")

    # ─── Index ────────────────────────────────────────────────────
    __table_args__ = (
        Index("idx_user_learning_profile_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<UserLearningProfile(user_id={self.user_id})>"
