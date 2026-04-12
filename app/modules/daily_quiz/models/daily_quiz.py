from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DATE, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class DailyQuiz(Base, TimestampMixin):
    __tablename__ = "daily_quiz"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_date = Column(DATE, nullable=False, unique=True, index=True)
    quiz_type = Column(
        String(20),
        nullable=False,
    )
    theme = Column(String(50), nullable=True, index=True)
    difficulte = Column(
        String(10),
        default="moyen",
        nullable=False,
    )
    nb_questions = Column(
        Integer,
        default=5,
        nullable=False,
    )
    questions_json = Column(JSONB, nullable=False)
    source = Column(
        String(10),
        default="llm",
        nullable=False,
    )
    llm_provider = Column(String(20), nullable=True)
    latence_generation_ms = Column(Integer, nullable=True)
    nb_tentatives = Column(
        Integer,
        default=0,
    )
    score_moyen = Column(Float, nullable=True)
    taux_completion = Column(Float, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "quiz_type IN ('qcm','qro','phrase_completion','true_false','ordering','matching')",
            name="ck_daily_quiz_quiz_type",
        ),
        CheckConstraint(
            "difficulte IN ('facile','moyen','difficile')",
            name="ck_daily_quiz_difficulte",
        ),
        CheckConstraint(
            "nb_questions BETWEEN 3 AND 15",
            name="ck_daily_quiz_nb_questions",
        ),
        CheckConstraint(
            "source IN ('llm','static','admin')",
            name="ck_daily_quiz_source",
        ),
        CheckConstraint(
            "nb_tentatives >= 0",
            name="ck_daily_quiz_nb_tentatives",
        ),
        CheckConstraint(
            "score_moyen BETWEEN 0 AND 100",
            name="ck_daily_quiz_score_moyen",
        ),
        CheckConstraint(
            "taux_completion BETWEEN 0 AND 1",
            name="ck_daily_quiz_taux_completion",
        ),
        Index("idx_date", "quiz_date"),
        Index("idx_theme_diff", "theme", "difficulte"),
    )

    attempts = relationship(
        "DailyQuizAttempt",
        back_populates="quiz",
        cascade="all, delete-orphan",
    )

    def get_questions_for_langue(self, langue: str = "fr", include_answers: bool = False) -> list:
        lang_questions = self.questions_json.get(langue, self.questions_json.get("fr", []))
        if not include_answers:
            return [
                {k: v for k, v in q.items() if k != "answer"}
                for q in lang_questions
            ]
        return lang_questions

    def serialize_public(self, langue: str = "fr") -> dict:
        return {
            "id": self.id,
            "quiz_date": str(self.quiz_date),
            "quiz_type": self.quiz_type,
            "theme": self.theme,
            "difficulte": self.difficulte,
            "nb_questions": self.nb_questions,
            "questions": self.get_questions_for_langue(langue, include_answers=False),
            "source": self.source,
            "nb_tentatives": self.nb_tentatives,
            "score_moyen": self.score_moyen,
            "taux_completion": self.taux_completion,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
