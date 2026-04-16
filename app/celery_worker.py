#!/usr/bin/env python3
"""
Start unified Celery worker for all KafkaLearn modules.
Usage: uv run python -m app.celery_worker
Or: celery -A app.celery_worker worker -l info -Q default,ingest,wisdom,users,notifications,payment,memory,epreuves,daily_quiz
"""
import os
os.environ.setdefault("OLLAMA_MODEL", "qwen2.5:7b")

# Import database_init to register ALL models (fixes cross-module relationship errors)
from app.core.database_init import init_db  # noqa: F401

from celery import Celery
from app.modules.core.config import settings

# Unified broker/backend
BROKER_URL = settings.REDIS_URL
BACKEND_URL = settings.REDIS_URL

app = Celery(
    "kafkalearn",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=[
        # Ingest
        "app.modules.ingest.jobs.tasks",
        "app.modules.ingest.jobs.ingest_folder_tasks",
        # Users
        "app.modules.users.jobs.tasks",
        # Wisdom
        "app.modules.wisdom.jobs.tasks",
        # Daily Quiz
        "app.modules.daily_quiz.jobs.tasks",
        # Memory
        "app.modules.memory.jobs.tasks",
        # Notifications
        "app.modules.notifications.jobs.tasks",
        # Payment
        "app.modules.payment.jobs.tasks",
        # Referral
        "app.modules.referral.jobs.tasks",
        # Skills
        "app.modules.skills.jobs.tasks",
        # Epreuves
        "app.modules.epreuves.jobs.tasks",
        # Calendar
        "app.modules.calendar.jobs.tasks",
        # User documents
        "app.modules.user_documents.jobs.tasks",
        # School
        # "app.modules.school.jobs.tasks",  # Import error: user_school module missing
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Douala",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Route tasks to queues (all to default for simplicity)
app.conf.task_routes = {
    "app.modules.*": {"queue": "default"},
}

if __name__ == "__main__":
    app.start()
