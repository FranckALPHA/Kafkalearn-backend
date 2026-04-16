"""
models/referral_activity.py
===========================
Tracks referral relationships and activation status.
"""
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    CheckConstraint,
    Index,
    ForeignKey,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class ReferralActivity(Base):
    __tablename__ = "referral_activities"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    referee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    date_ref = Column(TIMESTAMP, default=func.now(), nullable=False)
    date_activation = Column(TIMESTAMP, nullable=True)
    canal_acquisition = Column(
        String(20),
        CheckConstraint(
            "canal_acquisition IN ('lien_direct','qr_code','partage_whatsapp','sms','autre')"
        ),
        nullable=True,
    )
    recompense_appliquee = Column(Boolean, default=False, nullable=False)
    recompense_applied_at = Column(TIMESTAMP, nullable=True)

    # ─── Composite indexes ─────────────────────────────────────────
    __table_args__ = (
        Index("idx_referrer_active", "referrer_id", "is_active"),
        Index("idx_ref_date", "date_ref"),
        Index("idx_activation_date", "date_activation"),
    )

    # ─── Relationships ─────────────────────────────────────────────
    referrer = relationship("User", foreign_keys=[referrer_id], backref="referral_activities_sent")
    referee = relationship("User", foreign_keys=[referee_id], backref="referral_activities_received")

    # ─── Methods ───────────────────────────────────────────────────
    def serialize_for_list(self, mask_email: bool = True) -> dict:
        """Serialize for list responses with optional email masking."""
        referee_email = ""
        referee_prenom = ""
        if self.referee:
            if mask_email:
                email = self.referee.email or ""
                if "@" in email:
                    parts = email.split("@")
                    local = parts[0]
                    masked = local[:2] + "***" if len(local) > 2 else "***"
                    referee_email = f"{masked}@{parts[1]}"
                else:
                    referee_email = "***"
            else:
                referee_email = self.referee.email
            referee_prenom = self.referee.prenom or ""

        return {
            "id": self.id,
            "referee_id": str(self.referee_id),
            "referee_email": referee_email,
            "referee_prenom": referee_prenom,
            "date_ref": self.date_ref.isoformat() if self.date_ref else None,
            "date_activation": self.date_activation.isoformat() if self.date_activation else None,
            "est_actif": self.is_active,
            "canal": self.canal_acquisition,
            "recompense_appliquee": self.recompense_appliquee,
            "recompense_applied_at": self.recompense_applied_at.isoformat() if self.recompense_applied_at else None,
        }
