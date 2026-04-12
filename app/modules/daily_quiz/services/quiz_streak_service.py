import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from redis import Redis

from app.modules.daily_quiz.services.base import DailyQuizBaseService
from app.modules.daily_quiz.models import DailyQuizAttempt

logger = logging.getLogger(__name__)


class QuizStreakService(DailyQuizBaseService):
    async def calculer_streak_quiz(self, user_id) -> int:
        """Count consecutive days with quiz attempts up to today."""
        today = date.today()
        streak = 0
        current_day = today

        while True:
            count = (
                self.db.query(func.count(DailyQuizAttempt.id))
                .filter(
                    DailyQuizAttempt.user_id == user_id,
                    func.date(DailyQuizAttempt.created_at) == current_day,
                )
                .scalar()
            )
            if count > 0:
                streak += 1
                current_day -= timedelta(days=1)
            else:
                break

        return streak

    async def get_streak_info(self, user_id) -> dict:
        """Return current streak, longest streak, and last attempt date."""
        today = date.today()

        # Current streak
        current_streak = await self.calculer_streak_quiz(user_id)

        # Last attempt date
        last_attempt = (
            self.db.query(DailyQuizAttempt)
            .filter(DailyQuizAttempt.user_id == user_id)
            .order_by(DailyQuizAttempt.created_at.desc())
            .first()
        )
        last_attempt_date = None
        if last_attempt and last_attempt.created_at:
            last_attempt_date = last_attempt.created_at.date().isoformat()

        # Longest streak (computed from all attempt dates)
        attempt_dates = (
            self.db.query(func.date(DailyQuizAttempt.created_at))
            .filter(DailyQuizAttempt.user_id == user_id)
            .distinct()
            .order_by(func.date(DailyQuizAttempt.created_at).asc())
            .all()
        )
        attempt_dates = [row[0] for row in attempt_dates]

        longest_streak = 0
        temp_streak = 0
        prev_date = None
        for d in attempt_dates:
            if prev_date is None or (d - prev_date).days == 1:
                temp_streak += 1
            else:
                temp_streak = 1
            longest_streak = max(longest_streak, temp_streak)
            prev_date = d

        return {
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "last_attempt_date": last_attempt_date,
        }
