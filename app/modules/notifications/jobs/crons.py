"""
jobs/crons.py
=============
Celery Beat schedule for periodic notification tasks.
"""
from app.modules.notifications.jobs.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # Send quiz morning reminders every day at 7:00
    "quiz_morning": {
        "task": "app.modules.notifications.jobs.tasks.send_quiz_morning_task",
        "schedule": 3600.0,  # every hour; production should use crontab
        # "schedule": crontab(hour=7, minute=0),
    },
    # Send memory review reminders every day at 7:30
    "memory_reminders": {
        "task": "app.modules.notifications.jobs.tasks.send_memory_reminders_task",
        "schedule": 3600.0,
        # "schedule": crontab(hour=7, minute=30),
    },
    # Send streak danger warnings at 20:00
    "streak_danger": {
        "task": "app.modules.notifications.jobs.tasks.send_streak_danger_task",
        "schedule": 3600.0,
        # "schedule": crontab(hour=20, minute=0),
    },
    # Clean up invalid tokens every Sunday at 4:00
    "cleanup_tokens": {
        "task": "app.modules.notifications.jobs.tasks.cleanup_invalid_tokens_task",
        "schedule": 86400.0,
        # "schedule": crontab(hour=4, minute=0, day_of_week=0),
    },
    # Clean up old logs on the 1st of each month at 5:00
    "cleanup_logs": {
        "task": "app.modules.notifications.jobs.tasks.cleanup_old_logs_task",
        "schedule": 86400.0 * 30,
        # "schedule": crontab(hour=5, minute=0, day_of_month=1),
    },
}
