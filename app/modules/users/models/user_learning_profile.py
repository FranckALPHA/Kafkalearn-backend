"""
models/user_learning_profile.py
===============================
Profil cognitif de l'apprenant avec JSONB pour les données dynamiques.
"""
from sqlalchemy import Column, Integer, TIMESTAMP, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from .mixins import TimestampMixin


class UserLearningProfile(Base, TimestampMixin):
    __tablename__ = "user_learning_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True,
        nullable=False, index=True
    )

    # JSONB dynamiques (profil cognitif vivant)
    historique_recherches = Column(JSONB, default=list)  # FIFO 100
    lacunes = Column(JSONB, default=dict)  # {matiere: [notions]}
    forces = Column(JSONB, default=dict)
    interets = Column(JSONB, default=list)
    matieres_frequentes = Column(JSONB, default=dict)  # {matiere: count}
    intentions_recentes = Column(JSONB, default=list)  # FIFO 20
    skills_utilises = Column(JSONB, default=dict)
    sujets_vus = Column(JSONB, default=list)
    heures_actives = Column(JSONB, default=dict)  # {heure: count}
    jours_actifs = Column(JSONB, default=dict)  # {jour: count}
    score_par_matiere = Column(JSONB, default=dict)  # {matiere: score_moyen}

    last_wisdom_id = Column(Integer, nullable=True)
    dernier_rapport_at = Column(TIMESTAMP, nullable=True)

    # Relation
    user = relationship("User")

    # Index GIN pour recherches dans JSONB (PostgreSQL)
    __table_args__ = (
        Index("idx_lacunes_gin", "lacunes", postgresql_using="gin"),
        Index("idx_forces_gin", "forces", postgresql_using="gin"),
        Index("idx_score_matiere_gin", "score_par_matiere", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<UserLearningProfile(user_id={self.user_id})>"
