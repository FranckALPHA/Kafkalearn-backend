import secrets
import string

from sqlalchemy import Column, String, Text, Integer, Float, Boolean, TIMESTAMP, CheckConstraint, Index, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


def _generate_short_id() -> str:
    chars = string.ascii_uppercase + string.digits
    return "SCH-" + "".join(secrets.choice(chars) for _ in range(4))


def _generate_invitation_code() -> str:
    letters = string.ascii_uppercase
    alphanum = string.ascii_uppercase + string.digits
    part1 = "".join(secrets.choice(letters) for _ in range(3))
    part2 = "".join(secrets.choice(alphanum) for _ in range(3))
    return f"{part1}-{part2}"


class School(Base, TimestampMixin):
    __tablename__ = "schools"

    id = Column(String(8), primary_key=True, default=_generate_short_id)
    nom = Column(String(255), nullable=False)
    ville = Column(String(100), nullable=False)
    pays = Column(String(5), default="CM", nullable=False)
    region = Column(String(100), nullable=True, index=True)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    nb_eleves_max = Column(Integer, nullable=False)
    code_invitation = Column(String(10), unique=True, nullable=False, index=True, default=_generate_invitation_code)
    date_creation = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    date_expiration = Column(TIMESTAMP, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    logo_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    nb_eleves_actifs = Column(Integer, default=0)
    score_engagement_moyen = Column(Float, nullable=True)
    alerte_expiration_j7_envoyee = Column(Boolean, default=False, nullable=False)
    alerte_expiration_j3_envoyee = Column(Boolean, default=False, nullable=False)
    alerte_expiration_j1_envoyee = Column(Boolean, default=False, nullable=False)

    admin = relationship("User", foreign_keys=[admin_id])
    members = relationship("SchoolMember", back_populates="school", cascade="all, delete-orphan")
    ai_usage = relationship("SchoolAIUsage", back_populates="school", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("nb_eleves_max >= 10", name="ck_nb_eleves_max"),
        CheckConstraint("nb_eleves_actifs >= 0", name="ck_nb_eleves_actifs"),
        CheckConstraint("score_engagement_moyen BETWEEN 0 AND 100", name="ck_score_engagement"),
        Index("idx_active_expiration", "is_active", "date_expiration"),
        Index("idx_admin", "admin_id"),
        Index("idx_invitation", "code_invitation"),
    )

    @property
    def jours_restants(self) -> int:
        from datetime import datetime
        if self.date_expiration is None:
            return 0
        delta = self.date_expiration - datetime.utcnow()
        return max(0, delta.days)

    @property
    def is_trial(self) -> bool:
        return self.jours_restants < 30

    @property
    def places_restantes(self) -> int:
        return max(0, self.nb_eleves_max - self.nb_eleves_actifs)

    @property
    def nb_membres_actifs(self) -> int:
        from app.modules.school.models.school_member import SchoolMember
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            return db.query(SchoolMember).filter(
                SchoolMember.school_id == self.id,
                SchoolMember.is_active == True
            ).count()
        finally:
            db.close()

    def serialize_dashboard(self, is_admin: bool = False) -> dict:
        data = {
            "id": self.id,
            "nom": self.nom,
            "ville": self.ville,
            "pays": self.pays,
            "region": self.region,
            "admin_id": str(self.admin_id),
            "nb_eleves_max": self.nb_eleves_max,
            "code_invitation": self.code_invitation,
            "date_creation": self.date_creation.isoformat() if self.date_creation else None,
            "date_expiration": self.date_expiration.isoformat() if self.date_expiration else None,
            "is_active": self.is_active,
            "logo_url": self.logo_url,
            "description": self.description,
            "nb_eleves_actifs": self.nb_eleves_actifs,
            "score_engagement_moyen": self.score_engagement_moyen,
            "alerte_expiration_j7_envoyee": self.alerte_expiration_j7_envoyee,
            "alerte_expiration_j3_envoyee": self.alerte_expiration_j3_envoyee,
            "alerte_expiration_j1_envoyee": self.alerte_expiration_j1_envoyee,
            "jours_restants": self.jours_restants,
            "is_trial": self.is_trial,
            "places_restantes": self.places_restantes,
            "nb_membres_actifs": self.nb_membres_actifs,
        }
        if is_admin:
            data["pricing"] = {
                "nb_eleves_max": self.nb_eleves_max,
                "nb_eleves_actifs": self.nb_eleves_actifs,
                "score_engagement_moyen": self.score_engagement_moyen,
            }
        return data
