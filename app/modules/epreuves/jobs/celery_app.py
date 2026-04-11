from celery import Celery
from app.core.config import REDIS_URL

celery_app = Celery(
    "kafkalearn_epreuves",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Douala",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
