"""
jobs/crons.py
=============
Beat schedule for periodic Celery tasks in the ingest module.
"""

beat_schedule = {
    "retry_metadata_queue": {
        "task": "app.modules.ingest.jobs.tasks.reprocess_metadata_queue_task",
        "schedule": 7200.0,  # every 2 hours
        "options": {"expires": 3600},
    },
    "audit_pipeline_health": {
        "task": "app.modules.ingest.jobs.tasks.audit_pipeline_health_task",
        "schedule": 25200.0,  # every 7 hours (daily-ish)
        "options": {"expires": 7200},
    },
    "check_stuck_workers": {
        "task": "app.modules.ingest.jobs.tasks.check_stuck_workers_task",
        "schedule": 1800.0,  # every 30 minutes
        "options": {"expires": 900},
    },
}
