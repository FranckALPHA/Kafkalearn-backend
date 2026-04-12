"""
services/base.py
================
Classe de base pour les services du module wisdom.
"""
import logging
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)


class WisdomBaseService:
    """Classe mere avec utilitaires communs pour les services wisdom."""

    def __init__(self, db: Session, redis: Redis = None):
        self.db = db
        self.redis = redis or Redis.from_url(REDIS_URL, decode_responses=True, db=11)
