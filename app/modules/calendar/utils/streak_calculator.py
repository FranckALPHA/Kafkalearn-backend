"""
utils/streak_calculator.py
==========================
Calcul du streak d'étude (jours consécutifs).
"""
from datetime import datetime, timedelta, timezone
from typing import List


class StreakCalculator:
    MIN_SESSION_SECONDS = 300

    @classmethod
    def calculate_current_streak(cls, completed_sessions: list) -> int:
        if not completed_sessions:
            return 0
        now = datetime.now(timezone.utc)
        today = now.date()
        valid_dates = set()
        for s in completed_sessions:
            if s.accumulated_seconds >= cls.MIN_SESSION_SECONDS and s.actual_end:
                d = s.actual_end.date()
                if d <= today:
                    valid_dates.add(d)
        if not valid_dates:
            return 0
        streak = 0
        check = today
        while check in valid_dates:
            streak += 1
            check -= timedelta(days=1)
        return streak

    @classmethod
    def check_milestone(cls, old_streak: int, new_streak: int) -> List[int]:
        reached = []
        for m in [7, 14, 30, 60, 100, 180, 365]:
            if old_streak < m <= new_streak:
                reached.append(m)
        return reached
