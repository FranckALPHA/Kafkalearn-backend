"""
utils/quota_manager.py
======================
Gestion des quotas IA par plan utilisateur via Redis.
"""
from enum import Enum
from typing import Dict
from datetime import datetime, timedelta

from redis import Redis
from app.core.config import REDIS_URL


class IAQuota(Enum):
    FREEMIUM = {"daily": 5, "monthly": 50}
    ACCESS = {"daily": 20, "monthly": 300}
    PREMIUM = {"daily": 50, "monthly": 1000}
    PRO = {"daily": 200, "monthly": 5000}
    UNLIMITED = {"daily": -1, "monthly": -1}
    SCHOOL = {"daily": 100, "monthly": 3000}


class QuotaManager:
    """Gestion des quotas IA avec Redis pour le comptage en temps réel."""

    def __init__(self, redis_client: Redis = None):
        self.redis = redis_client or Redis.from_url(REDIS_URL, decode_responses=True, db=1)

    def _build_key(self, user_id: str, period: str) -> str:
        date_key = datetime.utcnow().strftime("%Y-%m-%d" if period == "daily" else "%Y-%m")
        return f"quota:{user_id}:{period}:{date_key}"

    async def check_and_consume(self, user_id: str, plan: str, cost: int = 1) -> bool:
        """Vérifie et consomme un quota IA. Retourne True si disponible."""
        try:
            quota_config = IAQuota[plan.upper()].value
        except KeyError:
            quota_config = IAQuota.FREEMIUM.value

        daily_key = self._build_key(user_id, "daily")
        monthly_key = self._build_key(user_id, "monthly")

        daily_used = int(self.redis.get(daily_key) or 0)
        monthly_used = int(self.redis.get(monthly_key) or 0)

        # Vérification daily
        if quota_config["daily"] >= 0 and daily_used + cost > quota_config["daily"]:
            return False

        # Vérification monthly
        if quota_config["monthly"] >= 0 and monthly_used + cost > quota_config["monthly"]:
            return False

        # Consommation atomique
        pipe = self.redis.pipeline()
        pipe.incrby(daily_key, cost)
        pipe.incrby(monthly_key, cost)

        # TTL daily: jusqu'à minuit prochain
        next_midnight = (datetime.utcnow().replace(hour=23, minute=59, second=59) + timedelta(hours=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        pipe.expireat(daily_key, int(next_midnight.timestamp()))

        # TTL monthly: fin du mois
        end_of_month = (datetime.utcnow().replace(day=1) + timedelta(days=32)).replace(day=1, hour=23, minute=59, second=59)
        pipe.expireat(monthly_key, int(end_of_month.timestamp()))

        pipe.execute()
        return True

    async def get_remaining(self, user_id: str, plan: str) -> Dict[str, int]:
        """Retourne les quotas restants daily/monthly."""
        try:
            quota_config = IAQuota[plan.upper()].value
        except KeyError:
            quota_config = IAQuota.FREEMIUM.value

        daily_key = self._build_key(user_id, "daily")
        monthly_key = self._build_key(user_id, "monthly")

        daily_used = int(self.redis.get(daily_key) or 0)
        monthly_used = int(self.redis.get(monthly_key) or 0)

        return {
            "daily": -1 if quota_config["daily"] < 0 else max(0, quota_config["daily"] - daily_used),
            "monthly": -1 if quota_config["monthly"] < 0 else max(0, quota_config["monthly"] - monthly_used),
            "daily_used": daily_used,
            "monthly_used": monthly_used,
        }
