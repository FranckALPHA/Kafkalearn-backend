import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from redis import Redis

from app.modules.daily_quiz.services.base import DailyQuizBaseService
from app.modules.daily_quiz.models import DailyQuiz, DailyQuizAttempt

logger = logging.getLogger(__name__)

REDIS_CACHE_KEY = "daily_quiz:last_difficulty"
REDIS_TTL_SECONDS = 86400  # 24h


class QuizAdaptivityService(DailyQuizBaseService):
    async def calculer_difficulte_pour_demain(self) -> str:
        """Determine difficulty for tomorrow's quiz based on last 3 days' average score."""
        # Check Redis cache first
        cached = self.redis.get(REDIS_CACHE_KEY)
        if cached:
            return cached

        try:
            today = date.today()
            three_days_ago = today - timedelta(days=3)

            avg_score = (
                self.db.query(func.avg(DailyQuizAttempt.score_pourcentage))
                .join(DailyQuiz, DailyQuizAttempt.daily_quiz_id == DailyQuiz.id)
                .filter(DailyQuiz.quiz_date >= three_days_ago)
                .filter(DailyQuiz.quiz_date < today)
                .scalar()
            )

            if avg_score is None:
                difficulty = "moyen"
            elif avg_score < 40:
                difficulty = "facile"
            elif avg_score <= 70:
                difficulty = "moyen"
            else:
                difficulty = "difficile"
        except Exception as exc:
            logger.error("Error calculating adaptive difficulty: %s", exc)
            difficulty = "moyen"

        # Cache in Redis
        self.redis.set(REDIS_CACHE_KEY, difficulty, ex=REDIS_TTL_SECONDS)

        return difficulty
