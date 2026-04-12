"""
jobs/crons.py
=============
Configuration Celery Beat pour les tâches planifiées du module payment.
"""
from celery.schedules import crontab

from app.modules.payment.jobs.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "expire_plans_daily": {
        "task": "payment.tasks.expire_individual_plans",
        "schedule": crontab(hour=0, minute=15),  # 0h15 chaque jour
        "options": {"queue": "cron"},
    },
    "calculate_mrr_daily": {
        "task": "payment.tasks.calculate_daily_mrr",
        "schedule": crontab(hour=1, minute=0),  # 1h00 chaque jour
        "options": {"queue": "cron"},
    },
    "detect_churn_weekly": {
        "task": "payment.tasks.detect_churn",
        "schedule": crontab(hour=7, minute=0, day_of_week=0),  # Dimanche 7h
        "options": {"queue": "cron"},
    },
}

celery_app.conf.task_routes = {
    "payment.tasks.notify_payment_complete": {"queue": "default"},
    "payment.tasks.validate_subscription": {"queue": "default"},
    "payment.tasks.expire_individual_plans": {"queue": "cron"},
    "payment.tasks.calculate_daily_mrr": {"queue": "cron"},
    "payment.tasks.detect_churn": {"queue": "cron"},
}
