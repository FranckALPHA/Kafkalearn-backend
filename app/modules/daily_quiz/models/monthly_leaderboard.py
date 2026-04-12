from sqlalchemy import Column, Integer, String, Float, TIMESTAMP, ForeignKey, CheckConstraint, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class MonthlyLeaderboard(Base, TimestampMixin):
    __tablename__ = "monthly_leaderboard"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month_year = Column(
        String(7),
        nullable=False,
        index=True,
    )
    total_score = Column(
        Integer,
        default=0,
    )
    nb_participations = Column(
        Integer,
        default=0,
    )
    nb_perfect_scores = Column(
        Integer,
        default=0,
    )
    meilleur_score_pct = Column(Float, nullable=True)
    rang = Column(Integer, nullable=True)
    rang_calcule_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "total_score >= 0",
            name="ck_monthly_leaderboard_total_score",
        ),
        CheckConstraint(
            "nb_participations >= 0",
            name="ck_monthly_leaderboard_nb_participations",
        ),
        CheckConstraint(
            "nb_perfect_scores >= 0",
            name="ck_monthly_leaderboard_nb_perfect_scores",
        ),
        CheckConstraint(
            "meilleur_score_pct BETWEEN 0 AND 100",
            name="ck_monthly_leaderboard_meilleur_score_pct",
        ),
        CheckConstraint(
            "rang > 0",
            name="ck_monthly_leaderboard_rang",
        ),
        UniqueConstraint("user_id", "month_year", name="idx_user_month_unique"),
        Index("idx_month_score", "month_year", "total_score"),
    )

    user = relationship(
        "User",
        back_populates="leaderboard_entries",
    )

    def serialize_ranking(self, user_prenom: str, user_classe: str) -> dict:
        pseudonymized_name = f"{user_prenom[0]}***" if user_prenom else "Anonyme"
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "user_prenom": pseudonymized_name,
            "user_classe": user_classe,
            "month_year": self.month_year,
            "total_score": self.total_score,
            "nb_participations": self.nb_participations,
            "nb_perfect_scores": self.nb_perfect_scores,
            "meilleur_score_pct": self.meilleur_score_pct,
            "rang": self.rang,
            "rang_calcule_at": self.rang_calcule_at.isoformat() if self.rang_calcule_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
