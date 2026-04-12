"""
utils/heartbeat_validator.py
============================
Validation sécurité des heartbeats (rate limit, delta, ownership).
"""
from datetime import datetime, timedelta, timezone
from redis import Redis
import logging

logger = logging.getLogger(__name__)


class HeartbeatValidator:
    MAX_PINGS_PER_MINUTE = 6
    MAX_DELTA_SECONDS = 60
    PAUSE_THRESHOLD_SECONDS = 900
    SESSION_EXPIRY_HOURS = 2

    def __init__(self, redis: Redis):
        self.redis = redis

    def _build_rate_key(self, session_id: int) -> str:
        return f"calendar:ping_rate:{session_id}"

    async def validate_ping(self, session, user_id: str, elapsed_client: int = None) -> dict:
        now = datetime.now(timezone.utc)

        # Ownership
        if str(session.user_id) != str(user_id):
            return {"allowed": False, "error": "NOT_OWNER"}

        # Session expiry
        if session.planned_end and session.planned_end + timedelta(hours=self.SESSION_EXPIRY_HOURS) < now:
            return {"allowed": False, "error": "SESSION_EXPIRED"}

        # Rate limiting
        rate_key = self._build_rate_key(session.id)
        current_count = self.redis.get(rate_key)
        if current_count and int(current_count) >= self.MAX_PINGS_PER_MINUTE:
            return {"allowed": False, "error": "RATE_LIMITED"}

        pipe = self.redis.pipeline()
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60)
        pipe.execute()

        # Delta since last ping
        last_ping = session.last_ping or session.actual_start or session.planned_start
        delta_seconds = int((now - last_ping).total_seconds()) if last_ping else 0

        is_pause_detected = delta_seconds > self.PAUSE_THRESHOLD_SECONDS

        if is_pause_detected:
            delta_to_count = 0
        else:
            delta_to_count = min(delta_seconds, self.MAX_DELTA_SECONDS)

        # Idempotence: duplicate ping within 5s
        if elapsed_client is not None and session.last_ping:
            time_since_last = (now - session.last_ping).total_seconds()
            if time_since_last < 5 and abs(elapsed_client - delta_seconds) < 2:
                return {"allowed": True, "delta_to_count": 0, "is_pause_detected": False, "is_duplicate": True}

        return {
            "allowed": True,
            "delta_to_count": delta_to_count,
            "is_pause_detected": is_pause_detected,
            "raw_delta_seconds": delta_seconds,
        }
