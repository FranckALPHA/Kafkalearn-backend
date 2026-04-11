"""
jobs/crons.py
=============
Configuration Celery Beat pour le module epreuves.
"""
from celery.schedules import crontab

# Cette configuration peut être ajoutée à l'app Celery principale
BEAT_SCHEDULE = {
    # Recalcul trending toutes les heures
    "epreuves:recalculate_trending_hourly": {
        "task": "epreuves.tasks.recalculate_trending",
        "schedule": crontab(minute=0),
        "options": {"queue": "cron"},
        "kwargs": {"periode_jours": 7},
    },
    # Nettoyage views anciennes (1er du mois à 2h)
    "epreuves:cleanup_old_views_monthly": {
        "task": "epreuves.tasks.cleanup_old_views",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
        "options": {"queue": "cron"},
    },
    # Alertes fichiers manquants quotidiennes (6h)
    "epreuves:alert_missing_files_daily": {
        "task": "epreuves.tasks.alert_missing_files",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "cron"},
    },
}
