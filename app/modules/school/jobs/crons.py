from celery.schedules import crontab

BEAT_SCHEDULE = {
    "school:check_expirations_daily": {
        "task": "school.tasks.check_school_expirations_task",
        "schedule": crontab(hour=8, minute=0),
        "options": {"queue": "cron"},
    },
    "school:expire_schools_daily": {
        "task": "school.tasks.expire_schools_task",
        "schedule": crontab(hour=0, minute=5),
        "options": {"queue": "cron"},
    },
    "school:calculate_engagement_daily": {
        "task": "school.tasks.calculate_engagement_task",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "cron"},
    },
    "school:consolidate_quota_daily": {
        "task": "school.tasks.consolidate_daily_quota_task",
        "schedule": crontab(hour=23, minute=55),
        "options": {"queue": "cron"},
    },
}
