from .tasks import generate_tomorrow_quiz_task, notify_quiz_available_task, calculate_monthly_ranks_task
from .celery_app import celery_app
__all__ = ["celery_app", "generate_tomorrow_quiz_task", "notify_quiz_available_task", "calculate_monthly_ranks_task"]
