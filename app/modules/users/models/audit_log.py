"""
models/audit_log.py
===================
Journal d'audit pour la sécurité et la conformité RGPD.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Index, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    actor_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )  # Qui a effectué l'action (peut être différent de user_id pour les admins)

    action = Column(String(100), nullable=False, index=True)  # login_failed, password_changed, profile_updated, etc.
    resource = Column(String(100), nullable=True)  # users, payments, documents, etc.
    resource_id = Column(String(50), nullable=True)

    details = Column(JSON, default=dict)  # Contexte détaillé
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    severity = Column(
        String(10), default="info", index=True,
        # info, warning, critical
    )

    created_at = func.now()

    # Relations
    user = relationship("User", foreign_keys=[user_id], back_populates="audit_logs")
    actor = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        Index("idx_audit_action_date", "action", "created_at"),
        Index("idx_audit_actor", "actor_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(action={self.action}, severity={self.severity})>"
