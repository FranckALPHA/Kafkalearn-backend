"""
models/refresh_token.py
=======================
Gestion des refresh tokens avec fingerprint device et révocation.
"""
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    token_jti = Column(String(50), unique=True, nullable=False, index=True)  # Unique JWT ID
    token_hash = Column(String(64), nullable=False)  # SHA256 hash du token complet
    fingerprint = Column(String(64), nullable=False, index=True)  # Device fingerprint
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    expires_at = Column(TIMESTAMP, nullable=False, index=True)
    revoked = Column(Boolean, default=False, nullable=False, index=True)
    revoked_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=func.now(), nullable=False)

    # Relations
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_user_active", "user_id", "revoked", "expires_at"),
    )

    def revoke(self):
        """Révoque ce refresh token."""
        self.revoked = True
        self.revoked_at = func.now()

    @property
    def is_valid(self) -> bool:
        from datetime import datetime
        return not self.revoked and func.now() < self.expires_at

    def __repr__(self) -> str:
        return f"<RefreshToken(user_id={self.user_id}, jti={self.token_jti})>"
