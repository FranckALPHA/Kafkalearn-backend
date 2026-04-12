"""
jobs/crons.py
=============
Celery Beat schedule for periodic daily quiz tasks.
"""
from app.modules.daily_quiz.jobs.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # Generate tomorrow's quiz every day at 22:00
    "generate_tomorrow_quiz": {
        "task": "app.modules.daily_quiz.jobs.tasks.generate_tomorrow_quiz_task",
        "schedule": 86400.0,  # daily; production should use crontab(hour=22, minute=0)
    },
    # Notify users quiz is available every day at 08:00
    "notify_quiz_available": {
        "task": "app.modules.daily_quiz.jobs.tasks.notify_quiz_available_task",
        "schedule": 86400.0,  # daily; production should use crontab(hour=8, minute=0)
    },
    # Calculate monthly ranks every day at 23:30
    "calculate_monthly_ranks": {
        "task": "app.modules.daily_quiz.jobs.tasks.calculate_monthly_ranks_task",
        "schedule": 86400.0,  # daily; production should use crontab(hour=23, minute=30)
    },
}
