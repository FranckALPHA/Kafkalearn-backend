"""
jobs/celery_app.py
==================
Configuration Celery pour le module skills.
Réutilise l'app Celery principale du module users.
"""
try:
    from app.modules.users.jobs.celery_app import celery_app
except ImportError:
    from celery import Celery
    from app.core.config import REDIS_URL

    celery_app = Celery("kafkalearn_skills", broker=REDIS_URL, backend=REDIS_URL)
