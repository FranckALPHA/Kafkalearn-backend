"""
services/notification_scheduler.py
====================================
Schedules future notifications using Redis keys with TTL.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from app.modules.notifications.services.base import NotificationBaseService

logger = logging.getLogger(__name__)

REDIS_PREFIX = "notif:scheduled:"
REDIS_TTL_SECONDS = 86400 * 7  # 7 days


class NotificationScheduler(NotificationBaseService):
    """Manages scheduled notifications via Redis."""

    def planifier_rappel_session(
        self,
        session_id,
        user_id,
        planned_start: datetime,
        subject: str,
    ):
        """Schedule a session reminder 15 minutes before planned_start."""
        remind_at = planned_start - timedelta(minutes=15)
        key = f"{REDIS_PREFIX}session_rappel:{session_id}"
        payload = json.dumps({
            "type": "session_rappel",
            "user_id": str(user_id),
            "session_id": str(session_id),
            "planned_start": planned_start.isoformat(),
            "remind_at": remind_at.isoformat(),
            "subject": subject,
        })
        if self.redis:
            self.redis.set(key, payload, ex=REDIS_TTL_SECONDS)
        logger.info("Scheduled session reminder for session %s at %s", session_id, remind_at)

    def planifier_revision_memory(
        self,
        user_id,
        section_id,
        next_review_at: datetime,
        nb_sections: int = 1,
    ):
        """Schedule a memory review reminder."""
        key = f"{REDIS_PREFIX}memory_review:{user_id}:{section_id}"
        payload = json.dumps({
            "type": "memory_review",
            "user_id": str(user_id),
            "section_id": str(section_id),
            "review_at": next_review_at.isoformat(),
            "nb_sections": nb_sections,
        })
        if self.redis:
            self.redis.set(key, payload, ex=REDIS_TTL_SECONDS)
        logger.info("Scheduled memory review for user %s, section %s", user_id, section_id)

    def annuler_rappel_session(self, session_id):
        """Cancel a scheduled session reminder."""
        key = f"{REDIS_PREFIX}session_rappel:{session_id}"
        if self.redis:
            self.redis.delete(key)
        logger.info("Cancelled session reminder for session %s", session_id)

    def get_due_notifications(self, type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all scheduled notifications that are due."""
        due = []
        if not self.redis:
            return due

        now = datetime.now()
        pattern = f"{REDIS_PREFIX}*"
        try:
            keys = list(self.redis.scan_iter(match=pattern, count=100))
        except Exception:
            return due

        for key in keys:
            try:
                raw = self.redis.get(key)
                if raw is None:
                    continue
                data = json.loads(raw)
                # Determine the trigger time key
                trigger_at_str = data.get("remind_at") or data.get("review_at")
                if trigger_at_str is None:
                    continue
                trigger_at = datetime.fromisoformat(trigger_at_str)
                if trigger_at <= now:
                    if type_filter is None or data.get("type") == type_filter:
                        due.append(data)
            except Exception as exc:
                logger.warning("Error parsing scheduled notif key %s: %s", key, exc)

        return due

    def mark_sent(self, key: str):
        """Mark a scheduled notification as sent by deleting the key."""
        if self.redis:
            self.redis.delete(f"{REDIS_PREFIX}{key}")
