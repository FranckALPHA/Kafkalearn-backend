"""
services/base.py
================
Classe de base pour tous les services du module users.
"""
from typing import List

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.users.utils.cache import redis_client


class BaseService:
    """Classe de base fournissant l'acces a la DB et Redis."""

    def __init__(self, db: Session, redis: Redis = None):
        self.db = db
        self.redis = redis or redis_client

    def _invalidate_profile_cache(self, user_id: str):
        """Invalide toutes les cles cache liees au profil d'un utilisateur."""
        keys = [
            f"user:profile:{user_id}",
            f"user:stats:{user_id}",
            f"user:learning-summary:{user_id}",
        ]
        if keys:
            self.redis.delete(*keys)
