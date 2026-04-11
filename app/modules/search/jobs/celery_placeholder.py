"""
jobs/celery_placeholder.py
==========================
Référence vers l'app Celery principale (définie dans users).
"""
# Import de l'app Celery principale depuis le module users
try:
    from app.modules.users.jobs.celery_app import celery_app
except ImportError:
    # Fallback si users n'est pas encore configuré
    from celery import Celery
    from app.core.config import REDIS_URL
    celery_app = Celery("kafkalearn", broker=REDIS_URL, backend=REDIS_URL)
