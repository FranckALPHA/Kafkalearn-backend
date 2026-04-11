"""
models/search_suggestion_cache.py
=================================
Cache persistant des suggestions personnalisées (TTL 24h).
"""
from sqlalchemy import Column, Integer, TIMESTAMP, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class SearchSuggestionCache(Base, TimestampMixin):
    __tablename__ = "search_suggestions_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True,
        nullable=False, index=True
    )

    suggestions = Column(JSONB, default=list, nullable=False)
    generated_at = Column(TIMESTAMP, default=func.now(), nullable=False)
    expires_at = Column(TIMESTAMP, nullable=False)

    # Relation
    user = relationship("User")

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def __repr__(self) -> str:
        return f"<SearchSuggestionCache(user_id={self.user_id}, expires={self.expires_at})>"
