"""
jobs/crons.py
=============
Celery Beat schedule for periodic memory tasks.
"""
from celery.schedules import crontab

beat_schedule = {
    "send_daily_review_reminders": {
        "task": "app.modules.memory.jobs.tasks.send_daily_review_reminders_task",
        "schedule": crontab(hour=7, minute=30),  # 7:30 daily
    },
    "regenerate_weekly_packs": {
        "task": "app.modules.memory.jobs.tasks.regenerate_weekly_packs_task",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),  # Monday 2:00
    },
    "update_item_difficulty": {
        "task": "app.modules.memory.jobs.tasks.update_item_difficulty_task",
        "schedule": crontab(hour=3, minute=0, day_of_week=3),  # Wednesday 3:00
    },
    "cleanup_orphans_monthly": {
        "task": "app.modules.memory.jobs.tasks.cleanup_orphans_monthly",
        "schedule": crontab(hour=4, minute=0, day_of_month=1),  # 1st of month 4:00
    },
    "extract_global_graph_from_documents": {
        "task": "app.modules.memory.jobs.tasks.extract_global_graph_from_documents_task",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2:00 (weekly)
    },
    "cleanup_stale_concept_edges": {
        "task": "app.modules.memory.jobs.tasks.cleanup_stale_concept_edges",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3:00
    },
    "retry_blocked_ingest_steps": {
        "task": "app.modules.ingest.jobs.ingest_folder_tasks.retry_blocked_ingest_steps",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
}
