"""
modules/core/redis_client.py
============================
Client Redis singleton.
"""
from redis import Redis

from app.modules.core.config import settings

redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True, db=0)


def get_redis() -> Redis:
    return redis_client
