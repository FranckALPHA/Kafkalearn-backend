"""
utils/rate_limiter.py
=====================
Middleware/Dep pour limiter les requêtes par IP via Redis.
"""
from fastapi import Request, HTTPException, status
from redis import Redis

from app.core.config import REDIS_URL

redis_client = Redis.from_url(REDIS_URL, decode_responses=True, db=1)


class RateLimiter:
    """
    Rate limiter basé sur Redis (sliding window counter).
    Limite : N requêtes par fenêtre glissante de M secondes.
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _get_client_ip(self, request: Request) -> str:
        """Extrait l'IP réelle derrière les proxies."""
        x_forwarded = request.headers.get("x-forwarded-for")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _build_key(self, endpoint: str, ip: str) -> str:
        return f"rate_limit:{endpoint}:{ip}"

    async def is_allowed(self, request: Request, endpoint: str) -> bool:
        ip = self._get_client_ip(request)
        key = self._build_key(endpoint, ip)

        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window_seconds)
        current_count, _ = pipe.execute()

        return current_count <= self.max_requests

    async def __call__(self, request: Request):
        endpoint = request.url.path.split("/")[-1] or "root"
        if not await self.is_allowed(request, endpoint):
            key = self._build_key(endpoint, self._get_client_ip(request))
            retry_after = redis_client.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="RATE_LIMIT_EXCEEDED",
                headers={"Retry-After": str(retry_after or self.window_seconds)},
            )


# Instances pré-configurées pour les endpoints sensibles
auth_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
register_rate_limiter = RateLimiter(max_requests=3, window_seconds=60)
password_reset_rate_limiter = RateLimiter(max_requests=3, window_seconds=300)  # 3/5min


def get_rate_limiter_dependency(limiter: RateLimiter):
    """Factory pour créer une dépendance FastAPI de rate limiting."""
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep
