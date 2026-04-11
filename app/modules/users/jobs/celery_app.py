"""
jobs/celery_app.py
==================
Configuration centrale de Celery + Redis broker/backend.
"""
from celery import Celery
from datetime import timedelta

from app.core.config import REDIS_URL

# Extraire l'host/port du REDIS_URL pour Celery
# redis://localhost:16379/0 -> redis://localhost:16379/0
celery_app = Celery(
    "kafkalearn",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Douala",
    enable_utc=True,

    # Retry automatique
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=30,
    task_max_retries=3,

    # Timeouts
    task_time_limit=300,
    task_soft_time_limit=240,
)

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "recalcul-scores-nocturne": {
        "task": "app.modules.users.jobs.tasks.nightly_score_recalc",
        "schedule": timedelta(hours=2),
        "options": {"queue": "cron"},
    },
    "detection-churn-matin": {
        "task": "app.modules.users.jobs.tasks.morning_churn_detection",
        "schedule": timedelta(hours=8),
        "options": {"queue": "cron"},
    },
    "nettoyage-tokens-expire": {
        "task": "app.modules.users.jobs.tasks.cleanup_expired_tokens",
        "schedule": timedelta(hours=6),
        "options": {"queue": "cron"},
    },
    "rapports-hebdomadaires": {
        "task": "app.modules.users.jobs.tasks.weekly_auto_reports",
        "schedule": timedelta(days=7),
        "options": {"queue": "cron"},
    },
}

celery_app.conf.task_routes = {
    "app.modules.users.jobs.tasks.send_otp_email": {"queue": "emails"},
    "app.modules.users.jobs.tasks.generate_pdf_report": {"queue": "heavy"},
    "app.modules.users.jobs.tasks.call_llm_for_summary": {"queue": "llm"},
    "app.modules.users.jobs.tasks.nightly_score_recalc": {"queue": "cron"},
    "app.modules.users.jobs.tasks.morning_churn_detection": {"queue": "cron"},
    "app.modules.users.jobs.tasks.cleanup_expired_tokens": {"queue": "cron"},
    "app.modules.users.jobs.tasks.weekly_auto_reports": {"queue": "cron"},
}
