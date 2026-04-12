"""
services/notification_service.py
=================================
Core notification sending, logging, and preference handling.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.modules.notifications.models import Device, NotificationLog, NotificationPreference
from app.modules.notifications.utils.firebase_client import FirebaseClient
from app.modules.notifications.utils.template_loader import TemplateLoader
from app.modules.notifications.utils.quiet_hours_checker import QuietHoursChecker
from app.modules.notifications.services.base import NotificationBaseService

logger = logging.getLogger(__name__)

# Attempt to import Celery tasks; fall back gracefully
try:
    from app.modules.notifications.jobs.tasks import send_push_notification_task as _celery_send_task
    CELERY_AVAILABLE = True
except ImportError:
    _celery_send_task = None  # type: ignore
    CELERY_AVAILABLE = False


class NotificationService(NotificationBaseService):
    """Primary service for sending and managing notifications."""

    def __init__(self, db: Session, redis=None):
        super().__init__(db, redis)
        self.firebase = FirebaseClient()
        self.templates = TemplateLoader()
        self.quiet_checker = QuietHoursChecker()

    # ─── Send to user ──────────────────────────────────────────────

    def send_to_user(
        self,
        user_id,
        title: str,
        body: str,
        type_notif: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
        skip_quiet_hours: bool = False,
    ) -> Dict[str, int]:
        """Send a push notification to all active devices of a user.

        Returns dict with nb_envoyes and nb_echecs.
        """
        devices = (
            self.db.query(Device)
            .filter(Device.user_id == user_id, Device.is_active == True)  # noqa: E712
            .all()
        )

        if not devices:
            return {"nb_envoyes": 0, "nb_echecs": 0}

        # Load preferences for type-checking
        prefs = (
            self.db.query(NotificationPreference)
            .filter(NotificationPreference.user_id == user_id)
            .first()
        )

        nb_envoyes = 0
        nb_echecs = 0

        for device in devices:
            # Check device-level filter
            if not device.should_receive(type_notif, preferences=prefs):
                continue

            # Check quiet hours
            if not skip_quiet_hours and prefs and prefs.is_quiet_hour():
                continue

            success, error = self.firebase.send_to_token(
                token=device.fcm_token,
                title=title,
                body=body,
                data=data,
                priority=priority,
            )

            notif_log = NotificationLog(
                user_id=user_id,
                title=title,
                body=body,
                type_notif=type_notif,
                data=data,
                fcm_success=success,
                fcm_error=str(error)[:100] if error else None,
            )
            self.db.add(notif_log)

            if success:
                nb_envoyes += 1
            else:
                nb_echecs += 1

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to commit notification logs for user %s", user_id)

        # Optionally enqueue via Celery for async processing
        if CELERY_AVAILABLE and _celery_send_task is not None:
            # Already sent synchronously; Celery task can be used for retries
            pass

        return {"nb_envoyes": nb_envoyes, "nb_echecs": nb_echecs}

    # ─── Template-based send ───────────────────────────────────────

    def envoyer_template(
        self,
        user_id,
        template_type: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, int]:
        """Render a template and send to user."""
        user = self.db.query(Device.user_id).filter(Device.id == user_id).first()
        device = self.db.query(Device).filter(Device.user_id == user_id).first()
        lang = device.langue if device else "fr"

        rendered = self.templates.render_template(template_type, params=params, lang=lang)
        if rendered is None:
            logger.warning("Template not found: %s (lang=%s)", template_type, lang)
            return {"nb_envoyes": 0, "nb_echecs": 0}

        # Enrich kwargs with notif type if not provided
        if "type_notif" not in kwargs:
            kwargs["type_notif"] = template_type

        return self.send_to_user(
            user_id=user_id,
            title=rendered["title"],
            body=rendered["body"],
            **kwargs,
        )

    # ─── Send to topic ─────────────────────────────────────────────

    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        type_notif: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """Send a push notification to an FCM topic."""
        success, error = self.firebase.send_to_topic(
            topic=topic,
            title=title,
            body=body,
            data=data,
        )

        # Log as a notification without user_id
        notif_log = NotificationLog(
            user_id=None,
            title=title,
            body=body,
            type_notif=type_notif,
            data=data,
            fcm_success=success,
            fcm_error=str(error)[:100] if error else None,
        )
        self.db.add(notif_log)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to commit topic notification log")

        return {"nb_envoyes": 1 if success else 0, "nb_echecs": 0 if success else 1}

    # ─── Read status ───────────────────────────────────────────────

    def mark_as_read(self, notif_id: int, user_id) -> bool:
        """Mark a notification as read. Returns True if updated."""
        notif = (
            self.db.query(NotificationLog)
            .filter(NotificationLog.id == notif_id, NotificationLog.user_id == user_id)
            .first()
        )
        if notif is None:
            return False
        notif.mark_as_opened()
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def mark_all_as_read(self, user_id) -> int:
        """Mark all unread notifications as read for a user. Returns count."""
        count = (
            self.db.query(NotificationLog)
            .filter(NotificationLog.user_id == user_id, NotificationLog.is_read == False)  # noqa: E712
            .update({NotificationLog.is_read: True, NotificationLog.opened_at: datetime.now()}, synchronize_session="fetch")
        )
        try:
            self.db.commit()
            return count
        except Exception:
            self.db.rollback()
            return 0

    # ─── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _is_type_enabled(preferences: NotificationPreference, notif_type: str) -> bool:
        """Check if a notification type is enabled in preferences."""
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
