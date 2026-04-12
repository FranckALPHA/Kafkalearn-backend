"""
services/base.py
================
Base service for referral operations with DB and Redis access.
"""
from sqlalchemy.orm import Session


class ReferralBaseService:
    """Base service providing DB and Redis connections."""

    def __init__(self, db: Session, redis=None):
        self.db = db
        if redis is None:
            try:
                from app.modules.core.redis_client import redis_client
                self.redis = redis_client
            except Exception:
                self.redis = None
        else:
            self.redis = redis
