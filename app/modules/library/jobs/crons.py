from celery.schedules import crontab

from app.modules.library.jobs.celery_app import celery_app

beat_schedule = {
    "recalculate_ratings_daily": {
        "task": "app.modules.library.jobs.tasks.recalculate_avg_ratings_task",
        "schedule": 4 * 3600,  # Every 4 hours
        "options": {"expires": 3600},
    },
    "cleanup_failed_weekly": {
        "task": "app.modules.library.jobs.tasks.cleanup_failed_assets_task",
        "schedule": crontab(hour=5, day_of_week=1),  # Monday at 5h
        "options": {"expires": 7200},
    },
    "calculate_admin_stats_daily": {
        "task": "app.modules.library.jobs.tasks.calculate_admin_stats_task",
        "schedule": crontab(hour=2, minute=0),  # Every day at 2h
        "options": {"expires": 3600},
    },
    "cleanup_orphan_copies_monthly": {
        "task": "app.modules.library.jobs.tasks.cleanup_orphan_copies_task",
        "schedule": crontab(hour=6, minute=0, day_of_month=1),  # 1st of month at 6h
        "options": {"expires": 7200},
    },
}

celery_app.conf.beat_schedule = beat_schedule
