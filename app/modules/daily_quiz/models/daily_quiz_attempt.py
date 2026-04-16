from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
    TIMESTAMP,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class DailyQuizAttempt(Base):
    __tablename__ = "daily_quiz_attempts"

    created_at = Column(TIMESTAMP, default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, default=func.now(), onupdate=func.now(), nullable=False
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    daily_quiz_id = Column(
        Integer,
        ForeignKey("daily_quiz.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score = Column(
        Integer,
        default=0,
    )
    score_pourcentage = Column(
        Float,
        default=0.0,
    )
    reponses_json = Column(
        JSONB,
        default=list,
        nullable=False,
    )
    duree_secondes = Column(Integer, nullable=True)
    langue = Column(
        String(5),
        default="fr",
        nullable=False,
    )
    is_complete = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "score >= 0",
            name="ck_daily_quiz_attempts_score",
        ),
        CheckConstraint(
            "score_pourcentage BETWEEN 0 AND 100",
            name="ck_daily_quiz_attempts_score_pourcentage",
        ),
        CheckConstraint(
            "duree_secondes IS NULL OR duree_secondes > 0",
            name="ck_daily_quiz_attempts_duree_secondes",
        ),
        UniqueConstraint("user_id", "daily_quiz_id", name="idx_user_quiz_unique"),
        Index("idx_quiz_score", "daily_quiz_id", "score_pourcentage"),
    )

    user = relationship(
        "User",
        back_populates="quiz_attempts",
        lazy="raise_on_sql",
    )
    quiz = relationship(
        "DailyQuiz",
        back_populates="attempts",
    )

    def serialize_result(self) -> dict:
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "daily_quiz_id": self.daily_quiz_id,
            "score": self.score,
            "score_pourcentage": self.score_pourcentage,
            "reponses": self.reponses_json,
            "duree_secondes": self.duree_secondes,
            "langue": self.langue,
            "is_complete": self.is_complete,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
