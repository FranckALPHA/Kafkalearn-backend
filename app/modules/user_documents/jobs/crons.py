"""
jobs/crons.py
=============
Celery Beat schedule for user_documents module.
"""
from datetime import timedelta
from celery.schedules import crontab

celery_beat_schedule = {
    "retry-failed-extractions": {
        "task": "app.modules.user_documents.jobs.tasks.retry_failed_extractions_cron",
        "schedule": timedelta(hours=3, minutes=30),
        "options": {"queue": "cron"},
    },
    "process-vectorization-queue": {
        "task": "app.modules.user_documents.jobs.tasks.vectorize_document_task",
        "schedule": timedelta(minutes=30),
        "options": {"queue": "cron"},
    },
    "cleanup-orphan-files-weekly": {
        "task": "app.modules.user_documents.jobs.tasks.cleanup_orphan_files_task",
        "schedule": crontab(hour=4, minute=30, day_of_week=0),
        "options": {"queue": "cron"},
    },
    "notify-inactive-monthly": {
        "task": "app.modules.user_documents.jobs.tasks.notify_inactive_documents_task",
        "schedule": crontab(hour=5, minute=30, day_of_month=1),
        "options": {"queue": "cron"},
    },
}
