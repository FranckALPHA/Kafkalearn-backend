"""
models/referral_reward.py
=========================
Tracks referral rewards (plan upgrades) granted to referrers.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, TIMESTAMP,
    CheckConstraint, Index, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class ReferralReward(Base, TimestampMixin):
    __tablename__ = "referral_rewards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    nb_filleuls_atteint = Column(
        Integer,
        CheckConstraint("nb_filleuls_atteint >= 3"),
        nullable=False,
    )
    plan_avant = Column(String(20), nullable=False)
    plan_apres = Column(String(20), nullable=False)
    duree_jours = Column(
        Integer,
        CheckConstraint("duree_jours > 0"),
        default=30,
        nullable=False,
    )
    expiration_at = Column(TIMESTAMP, nullable=False, index=True)

    # ─── Composite indexes ─────────────────────────────────────────
    __table_args__ = (
        Index("idx_user_expiration", "user_id", "expiration_at"),
    )

    # ─── Relationships ─────────────────────────────────────────────
    user = relationship("User", back_populates="referral_rewards")

    # ─── Properties ────────────────────────────────────────────────
    @property
    def jours_restants(self) -> int:
        """Return remaining days until reward expiration."""
        if self.expiration_at is None:
            return 0
        now = datetime.utcnow()
        if self.expiration_at < now:
            return 0
        delta = self.expiration_at - now
        return delta.days

    @property
    def is_active(self) -> bool:
        """Check if the reward is still active (not expired)."""
        if self.expiration_at is None:
            return False
        return datetime.utcnow() <= self.expiration_at

    # ─── Methods ───────────────────────────────────────────────────
    def serialize(self) -> dict:
        """Serialize reward data for API responses."""
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "nb_filleuls_atteint": self.nb_filleuls_atteint,
            "plan_avant": self.plan_avant,
            "plan_apres": self.plan_apres,
            "duree_jours": self.duree_jours,
            "expiration_at": self.expiration_at.isoformat() if self.expiration_at else None,
            "jours_restants": self.jours_restants,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
