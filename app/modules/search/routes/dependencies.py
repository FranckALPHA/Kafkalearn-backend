"""
routes/dependencies.py
======================
Dépendances FastAPI pour le module search.
"""
from fastapi import Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from functools import wraps

from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import RateLimiter

# Rate limiters pour search
search_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
search_lite_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
suggestion_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user = db.query(User).filter(
            User.id == payload.get("sub"),
            User.is_active == True,
            User.is_deleted == False,
        ).first()
        if not user:
            raise HTTPException(status_code=401, detail="USER_NOT_FOUND")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        return db.query(User).filter(
            User.id == payload.get("sub"),
            User.is_active == True,
            User.is_deleted == False,
        ).first()
    except Exception:
        return None


def get_search_orchestrator(db: Session = Depends(get_db)):
    from app.modules.search.services.search_orchestrator import SearchOrchestrator
    return SearchOrchestrator(db=db)


def get_analytics_service(db: Session = Depends(get_db)):
    from app.modules.search.services.search_analytics_service import SearchAnalyticsService
    return SearchAnalyticsService(db=db)


def get_suggestion_service(db: Session = Depends(get_db)):
    from app.modules.search.services.search_suggestion_service import SearchSuggestionService
    return SearchSuggestionService(db=db)


def get_rate_limiter_dependency(limiter: RateLimiter):
    """Factory pour créer une dépendance FastAPI de rate limiting."""
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep
