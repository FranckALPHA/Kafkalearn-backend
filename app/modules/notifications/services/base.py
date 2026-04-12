"""
services/base.py
================
Base service class for notification services.
"""
from typing import Optional

from sqlalchemy.orm import Session


class NotificationBaseService:
    """Base class shared by all notification services."""

    def __init__(self, db: Session, redis=None):
        self.db = db
        self.redis = redis
        if self.redis is None:
            try:
                from app.modules.core.redis_client import redis_client
                self.redis = redis_client
            except Exception:
                self.redis = None
