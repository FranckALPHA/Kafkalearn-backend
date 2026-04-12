from celery import Celery
from app.core.config import REDIS_URL
celery_app = Celery("kafkalearn_memory", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json", timezone="Africa/Douala", enable_utc=True)
