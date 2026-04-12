"""
app/modules/doc_analysis/jobs/crons.py
=======================================
Beat schedule for doc_analysis periodic tasks.
"""
from celery.schedules import crontab

beat_schedule = {
    "analyze_missing_documents": {
        "task": "doc_analysis.tasks.analyze_missing_documents",
        "schedule": crontab(minute=30, hour="*/1"),  # every 1h30 approx
        "options": {"queue": "heavy"},
        "kwargs": {"limit": 50, "langue": "fr"},
    },
    "verify_cache_coherence_weekly": {
        "task": "doc_analysis.tasks.verify_cache_coherence",
        "schedule": crontab(minute=0, hour=3, day_of_week=0),  # Sunday at 3h
        "options": {"queue": "default"},
    },
    "flush_access_counters": {
        "task": "doc_analysis.tasks.flush_access_counters",
        "schedule": crontab(minute="*/15"),  # every 15min
        "options": {"queue": "default"},
    },
}
