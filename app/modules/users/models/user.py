"""
models/user.py
==============
Entité principale Users avec mixins, contraintes, index optimisés.
"""
from sqlalchemy import (
    Column, String, Boolean, Float, Integer, TIMESTAMP,
    CheckConstraint, Index, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.core.database import Base
from .mixins import TimestampMixin, SoftDeleteMixin

# Import deferred for relationship (avoid circular)


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    # ─── Identité ────────────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)  # Argon2id, NULL si OAuth
    prenom = Column(String(100), nullable=True)
    nom = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    photo_url = Column(String(500), nullable=True)

    # ─── Profil scolaire ─────────────────────────────────────────
    langue = Column(
        String(5), nullable=False, default="fr",
        CheckConstraint("langue IN ('fr', 'en')")
    )
    classe = Column(String(50), nullable=True, index=True)
    serie = Column(String(20), nullable=True, index=True)
    region = Column(String(100), nullable=True, index=True)
    etablissement = Column(String(255), nullable=True)

    # ─── Sécurité & vérification ─────────────────────────────────
    email_verified = Column(Boolean, default=False, nullable=False)
    google_id = Column(String(255), unique=True, nullable=True)

    # ─── Plans & accès ───────────────────────────────────────────
    plan_base = Column(
        String(20), default="freemium", nullable=False,
        CheckConstraint(
            "plan_base IN ('freemium','access','premium','pro','unlimited','school')"
        )
    )
    plan_effectif = Column(
        String(20), default="freemium", nullable=False,
        CheckConstraint(
            "plan_effectif IN ('freemium','access','premium','pro','unlimited','school')"
        )
    )
    plan_expiration_at = Column(TIMESTAMP, nullable=True, index=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id"), nullable=True)

    # ─── Parrainage ──────────────────────────────────────────────
    referral_code = Column(String(10), unique=True, nullable=False, index=True)
    referred_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # ─── Engagement & scoring ────────────────────────────────────
    streak_jours = Column(Integer, default=0, CheckConstraint("streak_jours >= 0"))
    streak_max = Column(Integer, default=0, CheckConstraint("streak_max >= 0"))
    derniere_connexion_at = Column(TIMESTAMP, nullable=True, index=True)
    derniere_activite_at = Column(TIMESTAMP, nullable=True, index=True)

    onboarding_completed = Column(Boolean, default=False)
    niveau_estime = Column(
        String(10),
        CheckConstraint("niveau_estime IN ('faible','moyen','fort')")
    )
    matiere_forte = Column(String(100))
    matiere_faible = Column(String(100))

    score_global = Column(
        Float, default=0.0,
        CheckConstraint("score_global BETWEEN 0 AND 100")
    )
    progression_hebdo = Column(Float, default=0.0)

    # ─── Stats cumulées ──────────────────────────────────────────
    total_sessions_etude = Column(Integer, default=0)
    total_heures_etude = Column(Float, default=0.0)
    nb_quiz_reussis = Column(Integer, default=0)
    nb_quiz_echoues = Column(Integer, default=0)

    # ─── Session & sécurité ──────────────────────────────────────
    current_session_id = Column(String(36), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(
        String(20), default="student",
        CheckConstraint("role IN ('student','admin','superadmin')")
    )

    # ─── Relations ORM ───────────────────────────────────────────
    learning_profile = relationship(
        "UserLearningProfile", uselist=False, back_populates="user",
        cascade="all, delete-orphan"
    )
    activities = relationship("UserActivity", back_populates="user", lazy="dynamic")
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy="dynamic")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="dynamic")
    referred_users = relationship(
        "User", remote_side=[id], backref="referee"
    )
    roles = relationship(
        "Role", secondary="user_roles", back_populates="users", lazy="selectin"
    )

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_plan_activite", "plan_effectif", "derniere_activite_at"),
        Index("idx_classe_serie_langue", "classe", "serie", "langue"),
        Index("idx_referral", "referral_code", "referred_by_id"),
        Index("idx_churn", "plan_effectif", "derniere_activite_at", "is_active"),
    )

    # ─── Méthodes utilitaires ────────────────────────────────────
    @property
    def needs_onboarding(self) -> bool:
        return not self.onboarding_completed and not all([self.classe, self.serie, self.langue])

    def serialize_minimal(self) -> dict:
        """Sérialisation légère pour les réponses auth."""
        return {
            "id": str(self.id),
            "email": self.email,
            "prenom": self.prenom,
            "photo_url": self.photo_url,
            "plan_effectif": self.plan_effectif,
            "classe": self.classe,
            "serie": self.serie,
            "email_verified": self.email_verified,
            "onboarding_completed": self.onboarding_completed,
            "streak_jours": self.streak_jours,
            "score_global": self.score_global,
            "school_id": str(self.school_id) if self.school_id else None,
            "needs_onboarding": self.needs_onboarding,
        }

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
