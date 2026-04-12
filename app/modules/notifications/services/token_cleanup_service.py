"""
services/token_cleanup_service.py
===================================
Cleans up invalid or stale device tokens.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.notifications.models import Device
from app.modules.notifications.utils.firebase_client import FirebaseClient
from app.modules.notifications.services.base import NotificationBaseService

logger = logging.getLogger(__name__)


class TokenCleanupService(NotificationBaseService):
    """Deactivates devices with invalid FCM tokens and removes old records."""

    def cleanup_invalid_tokens(self) -> int:
        """Test tokens and deactivate devices with invalid ones.

        Returns count of deactivated devices.
        """
        firebase = FirebaseClient()
        devices = (
            self.db.query(Device)
            .filter(Device.is_active == True)  # noqa: E712
            .all()
        )

        deactivated = 0
        for device in devices:
            success, error = firebase.send_to_token(
                token=device.fcm_token,
                title="__ping__",
                body="Token validation",
                data={"type": "ping"},
            )
            if not success and firebase.is_invalid_token_error(str(error)):
                device.is_active = False
                deactivated += 1
                logger.info("Deactivated device %s: invalid token", device.id)

        if deactivated > 0:
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("Failed to commit token cleanup")

        return deactivated

    def cleanup_old_devices(self, days: int = 30) -> int:
        """Deactivate devices that have not been seen in `days` days.

        Returns count of deactivated devices.
        """
        cutoff = datetime.now() - timedelta(days=days)
        result = (
            self.db.query(Device)
            .filter(Device.is_active == True, Device.last_seen < cutoff)  # noqa: E712
            .update({Device.is_active: False}, synchronize_session="fetch")
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to commit old device cleanup")
        return result or 0
