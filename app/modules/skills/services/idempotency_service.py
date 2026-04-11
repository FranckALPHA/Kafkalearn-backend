"""
services/idempotency_service.py
===============================
Déduplication des requêtes skills via Redis.
"""
import logging
import hashlib
import json
from typing import Optional, Tuple
from datetime import datetime

from redis import Redis
from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)

IDEMPOTENCY_PREFIX = "skills:idempotency:"


class IdempotencyService:
    """Service d'idempotency pour éviter les exécutions doublons."""

    def __init__(self, redis: Redis = None):
        self.redis = redis or Redis.from_url(REDIS_URL, decode_responses=True, db=2)

    def generer_key_auto(self, user_id: str, prompt: str, skill_type: str) -> str:
        """Génère une clé d'idempotency automatique."""
        content = f"{user_id}:{skill_type}:{prompt.strip().lower()}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"idem_{skill_type}_{hash_val}"

    async def verifier_et_reserver(
        self, key: str, ttl_seconds: int = 60
    ) -> Tuple[bool, Optional[dict]]:
        """
        Vérifie si une requête est un doublon.

        Returns:
            (is_duplicate, previous_result)
            - is_duplicate=True et previous_result=le résultat précédent si existe
            - is_duplicate=False si nouvelle requête
        """
        full_key = f"{IDEMPOTENCY_PREFIX}{key}"

        # Vérifier si déjà complète
        stored = self.redis.get(f"{full_key}:result")
        if stored:
            try:
                return True, json.loads(stored)
            except json.JSONDecodeError:
                pass

        # Vérifier si en cours de traitement
        if self.redis.exists(f"{full_key}:processing"):
            return True, None

        # Réserver (marquer en cours)
        self.redis.setex(f"{full_key}:processing", ttl_seconds, "1")
        return False, None

    async def marquer_complete(self, key: str, result: dict, ttl_seconds: int = 300):
        """Marque une requête comme complète avec son résultat."""
        full_key = f"{IDEMPOTENCY_PREFIX}{key}"
        self.redis.setex(
            f"{full_key}:result",
            ttl_seconds,
            json.dumps(result, default=str),
        )
        # Supprimer le flag processing
        self.redis.delete(f"{full_key}:processing")

    async def liberrer_key(self, key: str):
        """Libère une clé en cas d'erreur (pour retry)."""
        full_key = f"{IDEMPOTENCY_PREFIX}{key}"
        self.redis.delete(f"{full_key}:processing")
        self.redis.delete(f"{full_key}:result")

    async def get_stored_result(self, key: str) -> Optional[dict]:
        """Récupère le résultat stocké si existe."""
        full_key = f"{IDEMPOTENCY_PREFIX}{key}"
        stored = self.redis.get(f"{full_key}:result")
        if stored:
            try:
                return json.loads(stored)
            except json.JSONDecodeError:
                pass
        return None
