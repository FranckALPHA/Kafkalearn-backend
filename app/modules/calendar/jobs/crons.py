"""
jobs/crons.py
=============
Celery Beat schedule pour le module calendar.
"""
from datetime import timedelta
from celery.schedules import crontab

from app.modules.calendar.jobs.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "calendar-sync-expired-sessions": {
        "task": "app.modules.calendar.jobs.tasks.sync_expired_sessions_task",
        "schedule": timedelta(seconds=900),  # 15 min
        "options": {"queue": "cron"},
    },
    "calendar-generate-daily-suggestions": {
        "task": "app.modules.calendar.jobs.tasks.generate_daily_suggestions_batch_task",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "default"},
    },
    "calendar-send-session-reminders-hourly": {
        "task": "app.modules.calendar.jobs.tasks.send_session_reminders_hourly_task",
        "schedule": timedelta(hours=1),
        "options": {"queue": "cron"},
    },
    "calendar-calculate-weekly-performance": {
        "task": "app.modules.calendar.jobs.tasks.calculate_weekly_performance_task",
        "schedule": crontab(hour=5, minute=0, day_of_week=6),  # Sunday 5h
        "options": {"queue": "cron"},
    },
}

celery_app.conf.task_routes = {
    "app.modules.calendar.jobs.tasks.sync_expired_sessions_task": {"queue": "cron"},
    "app.modules.calendar.jobs.tasks.send_session_reminders_hourly_task": {"queue": "cron"},
    "app.modules.calendar.jobs.tasks.calculate_weekly_performance_task": {"queue": "cron"},
    "app.modules.calendar.jobs.tasks.generate_daily_suggestions_batch_task": {"queue": "default"},
    "app.modules.calendar.jobs.tasks.log_user_activity_task": {"queue": "default"},
    "app.modules.calendar.jobs.tasks.update_user_study_stats_task": {"queue": "default"},
    "app.modules.calendar.jobs.tasks.send_session_reminder_task": {"queue": "default"},
    "app.modules.calendar.jobs.tasks.notify_streak_milestone_task": {"queue": "default"},
}
