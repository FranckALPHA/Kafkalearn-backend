"""
utils/cache.py
==============
Décorateurs et helpers pour le cache Redis.
"""
import json
import logging
from functools import wraps
from typing import Callable, Any, Optional
from redis import Redis

from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)

redis_client = Redis.from_url(REDIS_URL, decode_responses=True, db=1)


def cache_result(key_prefix: str, ttl_seconds: int = 600):
    """
    Décorateur pour mettre en cache le résultat d'une méthode asynchrone.

    Args:
        key_prefix: Préfixe pour la clé Redis (ex: "user:profile")
        ttl_seconds: Durée de vie du cache en secondes (défaut: 10min)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            instance = args[0] if args else None
            user_id = kwargs.get("user_id") or getattr(instance, "id", None)

            if not user_id:
                return await func(*args, **kwargs)

            cache_key = f"{key_prefix}:{user_id}"

            # Invalidation explicite
            if kwargs.get("invalidate") or kwargs.get("force_refresh"):
                redis_client.delete(cache_key)
                kwargs.pop("invalidate", None)
                kwargs.pop("force_refresh", None)

            # Lecture cache
            cached = redis_client.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    redis_client.delete(cache_key)

            # Exécution réelle
            result = await func(*args, **kwargs)

            # Écriture cache
            try:
                redis_client.setex(cache_key, ttl_seconds, json.dumps(result, default=str))
            except (TypeError, ValueError) as e:
                logger.warning(f"Cache write failed for {cache_key}: {e}")

            return result
        return wrapper
    return decorator


def invalidate_cache(key_prefix: str, user_id: str):
    """Invalide explicitement une clé de cache."""
    cache_key = f"{key_prefix}:{user_id}"
    redis_client.delete(cache_key)

    # Invalider aussi les clés dérivées
    pattern = f"{key_prefix}:{user_id}:*"
    for key in redis_client.scan_iter(match=pattern):
        redis_client.delete(key)


def get_cached(key: str) -> Optional[Any]:
    """Lit une valeur du cache."""
    cached = redis_client.get(key)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return None
    return None


def set_cached(key: str, value: Any, ttl_seconds: int = 600):
    """Écrit une valeur dans le cache."""
    try:
        redis_client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except (TypeError, ValueError) as e:
        logger.warning(f"Cache write failed for {key}: {e}")
