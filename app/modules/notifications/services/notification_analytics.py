"""
services/notification_analytics.py
====================================
Analytics and statistics for notifications.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.modules.notifications.models import NotificationLog, Device
from app.modules.notifications.services.base import NotificationBaseService

logger = logging.getLogger(__name__)


class NotificationAnalytics(NotificationBaseService):
    """Provides notification statistics and analytics."""

    def get_stats(self, period: str = "7d") -> Dict[str, Any]:
        """Return notification statistics for the given period.

        Args:
            period: e.g. '7d', '30d', '1d'

        Returns:
            dict with total_sent, total_opened, open_rate, by_type, by_platform
        """
        # Parse period
        if period.endswith("d"):
            days = int(period[:-1])
        else:
            days = 7

        cutoff = datetime.now() - timedelta(days=days)

        # Total sent and opened
        total_sent = (
            self.db.query(sa_func.count(NotificationLog.id))
            .filter(NotificationLog.created_at >= cutoff)
            .scalar() or 0
        )

        total_opened = (
            self.db.query(sa_func.count(NotificationLog.id))
            .filter(
                NotificationLog.created_at >= cutoff,
                NotificationLog.is_read == True,  # noqa: E712
            )
            .scalar() or 0
        )

        open_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0.0

        # By type
        by_type_rows = (
            self.db.query(NotificationLog.type_notif, sa_func.count(NotificationLog.id))
            .filter(NotificationLog.created_at >= cutoff)
            .group_by(NotificationLog.type_notif)
            .all()
        )
        by_type = {row[0]: row[1] for row in by_type_rows}

        # By platform (join with Device)
        by_platform_rows = (
            self.db.query(Device.platform, sa_func.count(NotificationLog.id))
            .join(Device, Device.user_id == NotificationLog.user_id, isouter=True)
            .filter(NotificationLog.created_at >= cutoff)
            .group_by(Device.platform)
            .all()
        )
        by_platform = {row[0] or "unknown": row[1] for row in by_platform_rows}

        return {
            "total_sent": total_sent,
            "total_opened": total_opened,
            "open_rate": round(open_rate, 2),
            "by_type": by_type,
            "by_platform": by_platform,
            "period": period,
        }

    def get_user_unread_count(self, user_id) -> int:
        """Return the number of unread notifications for a user."""
        return (
            self.db.query(sa_func.count(NotificationLog.id))
            .filter(
                NotificationLog.user_id == user_id,
                NotificationLog.is_read == False,  # noqa: E712
            )
            .scalar() or 0
        )
