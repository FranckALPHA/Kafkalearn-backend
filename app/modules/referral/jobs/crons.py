"""
jobs/crons.py
=============
Celery Beat schedule for periodic referral tasks.
"""

celery_beat_schedule = {
    "check_expired_rewards_daily": {
        "task": "app.modules.referral.jobs.tasks.check_expired_rewards_task",
        "schedule": 3600,  # Every hour
        "options": {"expires": 3600},
    },
    "sync_active_referees_daily": {
        "task": "app.modules.referral.jobs.tasks.sync_active_referees_task",
        "schedule": 7200,  # Every 2 hours
        "options": {"expires": 7200},
    },
}
