"""
models/user_learning_signals.py
===============================
4 couches de signaux d'apprentissage — ce que le système sait SUR l'utilisateur,
au-delà de ce qu'il déclare dans son profil.

Architecture :
  1. Temporel    : habitudes horaires, streak, rythme
  2. Comportemental : comment il interagit (abandon, persistance, préférences)
  3. Cognitif    : lacunes profondes vs superficielles (via SM-2 + graphe)
  4. Contextuel  : urgence, mode d'apprentissage, contraintes
"""
from sqlalchemy import (
    Column, Integer, Float, Boolean, String, Text, ForeignKey,
    CheckConstraint, Index, UniqueConstraint, TIMESTAMP, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class UserLearningSignals(Base, TimestampMixin):
    """
    Une seule ligne par utilisateur. Chaque couche est un JSONB autonome
    qui grossit au fil du temps. Le Coach IA lit tout ça pour décider.
    """
    __tablename__ = "user_learning_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True
    )

    # ─── COUCHE 1 : Temporel ─────────────────────────────────────
    # Rythmes d'apprentissage naturels de l'utilisateur
    temporal_signals = Column(JSONB, default=dict)
    # {
    #   "preferred_hours": {"20": 5, "21": 8, "22": 3},  # heure → nb sessions
    #   "preferred_days": {"lundi": 4, "mardi": 6, ...},
    #   "avg_session_duration_min": 25,
    #   "longest_streak": 12,
    #   "current_streak": 3,
    #   "last_active_at": "2026-04-13T21:00:00",
    #   "consistency_score": 0.72,  # régularité (0-1)
    #   "morning_person": false,
    #   "exam_deadline": "2026-06-15"  # si connu via chat
    # }

    # ─── COUCHE 2 : Comportemental ───────────────────────────────
    # Comment l'utilisateur interagit avec le système
    behavioral_signals = Column(JSONB, default=dict)
    # {
    #   "profile_type": "practical",  # "theoretical" | "practical" | "mixed"
    #   "content_preference": "exercises",  # "fiches" | "exercises" | "videos" | "mixed"
    #   "quit_rate_hard": 0.35,  # taux d'abandon sur contenu difficile
    #   "quit_rate_easy": 0.05,  # taux d'abandon sur contenu facile
    #   "avg_time_before_answer_sec": 12,  # réflexif (>15s) ou impulsif (<5s)
    #   "retry_after_failure": true,  # réessaie après un échec
    #   "seeks_explanations": false,  # demande souvent "pourquoi"
    #   "preferred_difficulty": "medium",  # évite le trop dur ou cherche le défi
    #   "frustration_triggers": ["long_texts", "no_visual_aids"]
    # }

    # ─── COUCHE 3 : Cognitif ─────────────────────────────────────
    # Méta-analyse des performances — au-delà du graphe brut
    cognitive_signals = Column(JSONB, default=dict)
    # {
    #   "deep_blockages": {
    #     "derivees": {"weeks_stuck": 3, "attempts": 8, "best_score": 42, "sm2_ef_trend": "decreasing"}
    #   },
    #   "superficial_gaps": {
    #     "integrales": {"attempts": 2, "best_score": 55, "improving": true}
    #   },
    #   "learning_velocity": {"Mathematiques": -0.05, "SVT": 0.12},  # pente de progression
    #   "zone_proximale": {"Mathematiques": "equations", "Physique": "forces"},  # prochain cran
    #   "meta_awareness": 0.6,  # écart entre ce qu'il croit savoir et ce qu'il sait
    #   "transfer_ability": "low"  # capacité à appliquer un concept dans un autre contexte
    # }

    # ─── COUCHE 4 : Contextuel ────────────────────────────────────
    # Mode urgence, contraintes, déclarations explicites
    contextual_signals = Column(JSONB, default=dict)
    # {
    #   "urgency_mode": false,  # examen imminent → mode intensif
    #   "days_until_exam": null,
    #   "learning_mode": "autodidact",  # "guided" | "autodidact" | "hybrid"
    #   "explicit_preferences": {
    #     "prefers_schemas": true,
    #     "hates_long_texts": false,
    #     "likes_quizzes": true
    #   },
    #   "life_constraints": ["works_evenings", "no_internet_weekends"],
    #   "motivation_level": 0.7,  # déduit du comportement
    #   "recent_life_events": ["mentioned_exam_stress"]  # détecté via chat
    # }

    # ─── Relation ────────────────────────────────────────────────
    user = relationship("User")

    # ─── Index ───────────────────────────────────────────────────
    __table_args__ = (
        Index("idx_uls_user", "user_id"),
        Index("idx_uls_temporal_gin", "temporal_signals", postgresql_using="gin"),
        Index("idx_uls_cognitive_gin", "cognitive_signals", postgresql_using="gin"),
    )

    def serialize(self) -> dict:
        return {
            "user_id": str(self.user_id),
            "temporal": self.temporal_signals or {},
            "behavioral": self.behavioral_signals or {},
            "cognitive": self.cognitive_signals or {},
            "contextual": self.contextual_signals or {},
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserLearningSignals(user={self.user_id})>"
