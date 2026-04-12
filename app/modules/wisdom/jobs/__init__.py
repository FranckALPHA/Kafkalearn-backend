from .tasks import generate_wisdom_task, send_morning_notification_task, recalculate_ratings_task
from .celery_app import celery_app
__all__ = ["celery_app", "generate_wisdom_task", "send_morning_notification_task", "recalculate_ratings_task"]
