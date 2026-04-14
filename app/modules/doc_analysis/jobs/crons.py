"""
app/modules/doc_analysis/jobs/crons.py
=======================================
Beat schedule for doc_analysis periodic tasks. Bilingue FR/EN.
"""
from celery.schedules import crontab

beat_schedule = {
    "analyze_missing_documents_fr": {
        "task": "doc_analysis.tasks.analyze_missing_documents",
        "schedule": crontab(minute=30, hour="*/2"),
        "options": {"queue": "heavy"},
        "kwargs": {"limit": 50, "langue": "fr"},
    },
    "analyze_missing_documents_en": {
        "task": "doc_analysis.tasks.analyze_missing_documents",
        "schedule": crontab(minute=0, hour="*/2"),
        "options": {"queue": "heavy"},
        "kwargs": {"limit": 50, "langue": "en"},
    },
    "verify_cache_coherence_weekly": {
        "task": "doc_analysis.tasks.verify_cache_coherence",
        "schedule": crontab(minute=0, hour=3, day_of_week=0),
        "options": {"queue": "default"},
    },
    "flush_access_counters": {
        "task": "doc_analysis.tasks.flush_access_counters",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "default"},
    },
}
