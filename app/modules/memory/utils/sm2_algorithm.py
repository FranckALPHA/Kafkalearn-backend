from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class SM2Result:
    next_review_date: datetime
    interval_days: int
    easiness_factor: float
    was_success: bool


class SM2Algorithm:
    INITIAL_INTERVAL = 1
    SECOND_INTERVAL = 6
    EF_MIN = 1.3
    EF_START = 2.5

    @classmethod
    def calculate(
        cls,
        quality: int,
        current_ef: float = EF_START,
        current_interval: int = 1,
        repetition_count: int = 0,
        review_date: Optional[datetime] = None,
    ) -> SM2Result:
        review_date = review_date or datetime.now(timezone.utc)
        was_success = quality >= 3

        if not was_success:
            return SM2Result(
                next_review_date=review_date + timedelta(days=1),
                interval_days=1,
                easiness_factor=current_ef,
                was_success=False,
            )

        if repetition_count == 0:
            new_interval = cls.INITIAL_INTERVAL
        elif repetition_count == 1:
            new_interval = cls.SECOND_INTERVAL
        else:
            new_interval = round(current_interval * current_ef)

        new_ef = current_ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        new_ef = max(cls.EF_MIN, new_ef)

        return SM2Result(
            next_review_date=review_date + timedelta(days=new_interval),
            interval_days=new_interval,
            easiness_factor=new_ef,
            was_success=True,
        )

    @staticmethod
    def quality_from_score(score_percent: float) -> int:
        if score_percent >= 100:
            return 5
        elif score_percent >= 90:
            return 4
        elif score_percent >= 70:
            return 3
        elif score_percent >= 40:
            return 2
        elif score_percent >= 10:
            return 1
        return 0
