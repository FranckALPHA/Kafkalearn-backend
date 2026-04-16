"""
models/user_activity.py
=======================
Suivi des activités utilisateur pour analytics et streaks.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Index, JSON, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserActivity(Base):
    __tablename__ = "user_activities"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    action = Column(String(100), nullable=False, index=True)  # login, quiz, search, etc.
    details = Column(JSON, default=dict)  # metadata contextuelle
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Relation
    user = relationship("User")

    # Index pour les requêtes par user + date
    __table_args__ = (
        Index("idx_user_activity_user_date", "user_id", "created_at"),
        Index("idx_user_activity_action", "user_id", "action"),
    )

    def __repr__(self) -> str:
        return f"<UserActivity(user_id={self.user_id}, action={self.action})>"
