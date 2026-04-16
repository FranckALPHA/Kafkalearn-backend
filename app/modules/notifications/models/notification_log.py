"""
models/notification_log.py
==========================
Notification log for tracking sent notifications and read status.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    TIMESTAMP,
    Index,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    body = Column(String(1000), nullable=False)
    type_notif = Column(String(30), nullable=False, index=True)
    data = Column(JSONB, default=dict, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    fcm_success = Column(Boolean, nullable=True)
    fcm_error = Column(String(100), nullable=True)
    opened_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        Index("idx_notification_user_created", "user_id", "created_at"),
        Index("idx_type_read", "type_notif", "is_read"),
        Index("idx_unread_users", "user_id", "is_read", "created_at"),
    )

    user = relationship("User")

    def serialize_for_history(self):
        """Return dict suitable for API response."""
        return {
            "id": self.id,
            "user_id": str(self.user_id) if self.user_id else None,
            "title": self.title,
            "body": self.body,
            "type_notif": self.type_notif,
            "data": self.data or {},
            "is_read": self.is_read,
            "fcm_success": self.fcm_success,
            "fcm_error": self.fcm_error,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def mark_as_opened(self):
        """Mark notification as opened."""
        from sqlalchemy import func as sa_func

        self.is_read = True
        self.opened_at = sa_func.now()
