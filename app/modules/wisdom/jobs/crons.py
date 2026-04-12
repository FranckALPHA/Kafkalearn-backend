"""
jobs/crons.py
=============
Beat schedule pour les taches periodiques du module wisdom.
"""
from celery.schedules import crontab

BEAT_SCHEDULE = {
    "generate_tomorrow_wisdom": {
        "task": "wisdom.generate_wisdom_task",
        "schedule": crontab(hour=23, minute=0),
        "args": [],
        "options": {"expires": 3600},
    },
    "send_morning_notification": {
        "task": "wisdom.send_morning_notification_task",
        "schedule": crontab(hour=7, minute=0),
        "options": {"expires": 3600},
    },
    "recalculate_ratings": {
        "task": "wisdom.recalculate_ratings_task",
        "schedule": crontab(hour=5, minute=0),
        "options": {"expires": 7200},
    },
}
