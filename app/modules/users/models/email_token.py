"""
models/email_token.py
=====================
Tokens OTP pour la vérification d'email et reset de mot de passe.
"""
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class EmailToken(Base):
    __tablename__ = "email_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    token = Column(String(6), nullable=False)  # Code OTP à 6 chiffres
    token_type = Column(
        String(20), nullable=False, index=True,
        # Types: email_verify, password_reset, login_otp
    )
    expires_at = Column(TIMESTAMP, nullable=False, index=True)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, default=func.now(), nullable=False)

    # Relation
    user = relationship("User")

    __table_args__ = (
        Index("idx_email_token_user_type", "user_id", "token_type"),
        Index("idx_email_token_expires", "expires_at", "used"),
    )

    @property
    def is_expired(self) -> bool:
        from datetime import datetime
        return func.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.used and not self.is_expired

    def __repr__(self) -> str:
        return f"<EmailToken(user_id={self.user_id}, type={self.token_type})>"
