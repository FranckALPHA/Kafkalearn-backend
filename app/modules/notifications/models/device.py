"""
models/device.py
================
Device entity for push notification tokens and device metadata.
"""
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, TIMESTAMP,
    CheckConstraint, Index, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class Device(Base, TimestampMixin):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fcm_token = Column(Text, unique=True, nullable=False, index=True)
    platform = Column(
        String(10),
        CheckConstraint("platform IN ('android', 'ios', 'web')"),
        nullable=False,
    )
    app_version = Column(String(20), nullable=True)
    device_model = Column(String(100), nullable=True)
    classe = Column(String(50), nullable=True, index=True)
    serie = Column(String(20), nullable=True, index=True)
    langue = Column(
        String(5),
        CheckConstraint("langue IN ('fr', 'en')"),
        nullable=False,
        default="fr",
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    notifs_enabled = Column(Boolean, default=True, nullable=False)
    topics_souscrits = Column(JSONB, default=list, nullable=False)
    last_seen = Column(TIMESTAMP, default=func.now(), nullable=False, index=True)

    __table_args__ = (
        Index("idx_device_user_active", "user_id", "is_active"),
        Index("idx_platform_langue", "platform", "langue"),
        Index("idx_classe_serie", "classe", "serie"),
    )

    user = relationship("User")

    def serialize_for_topics(self):
        """Return list of FCM topics this device should subscribe to."""
        topics = []
        lang = self.langue or "fr"
        topics.append(f"announcements_{lang}")
        topics.append(f"memory_{lang}")
        topics.append(f"quiz_{lang}")
        if self.classe:
            topics.append(f"classe_{self.classe}")
        if self.serie:
            topics.append(f"serie_{self.serie}")
        return topics

    def should_receive(self, notif_type, preferences=None):
        """Check if this device should receive a given notification type."""
        if not self.is_active or not self.notifs_enabled:
            return False
        if preferences is None:
            return True
        type_to_pref = {
            "quiz_dispo": "quiz_dispo",
            "memory_review": "memory_review",
            "session_rappel": "session_rappel",
            "streak_danger": "streaks",
            "payment_confirm": "payment",
            "lacune_detectee": "lacunes",
            "annonce": None,
            "referral_actif": None,
            "referral_reward": None,
        }
        pref_key = type_to_pref.get(notif_type)
        if pref_key is None:
            return True
        return getattr(preferences, pref_key, True)
