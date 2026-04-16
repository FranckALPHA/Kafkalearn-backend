from datetime import datetime, timezone

from sqlalchemy import Column, ForeignKey, Integer, TIMESTAMP, DATE, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class DailySuggestionsCache(Base):
    __tablename__ = "daily_suggestions_cache"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date_suggestion = Column(DATE, nullable=False, index=True)
    suggestions_json = Column(JSONB, nullable=False)
    matieres_du_jour = Column(JSONB, nullable=False)
    generated_at = Column(TIMESTAMP, default=func.now())

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)
        if not self.updated_at:
            self.updated_at = datetime.now(timezone.utc)


    __table_args__ = (
        UniqueConstraint(
            "user_id", "date_suggestion",
            name="uq_user_date_suggestion"
        ),
        Index("idx_date_active", "date_suggestion", "generated_at"),
    )

    user = relationship("User")

    @property
    def is_expired(self) -> bool:
        today = datetime.now(timezone.utc).date() if self.date_suggestion else datetime.now().date()
        return self.date_suggestion < today if self.date_suggestion else True

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "date_suggestion": self.date_suggestion.isoformat() if self.date_suggestion else None,
            "suggestions_json": self.suggestions_json,
            "matieres_du_jour": self.matieres_du_jour,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
