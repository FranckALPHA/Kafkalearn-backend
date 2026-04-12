from sqlalchemy import Column, String, Integer, DATE, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class SchoolAIUsage(Base):
    __tablename__ = "school_ai_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    school_id = Column(String(8), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DATE, nullable=False, index=True)
    quota_total = Column(Integer, nullable=False)
    quota_consomme = Column(Integer, default=0)
    nb_utilisateurs_actifs = Column(Integer, default=0)

    school = relationship("School", back_populates="ai_usage")

    __table_args__ = (
        CheckConstraint("quota_consomme >= 0", name="ck_quota_consomme"),
        CheckConstraint("nb_utilisateurs_actifs >= 0", name="ck_nb_utilisateurs_actifs"),
        UniqueConstraint("school_id", "date", name="idx_school_date_unique"),
    )

    @property
    def quota_restant(self) -> int:
        return max(0, self.quota_total - self.quota_consomme)

    @property
    def taux_utilisation(self) -> float:
        if self.quota_total == 0:
            return 0.0
        return round((self.quota_consomme / self.quota_total) * 100, 2)
