"""
models/mixins.py
================
Mixins SQLAlchemy pour la gestion commune des modèles.
"""
from sqlalchemy import Column, Boolean, func, TIMESTAMP

class TimestampMixin:
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

class SoftDeleteMixin:
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    def soft_delete(self):
        self.is_deleted = True
