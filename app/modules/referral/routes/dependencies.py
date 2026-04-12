"""
routes/dependencies.py
======================
Dependency injection for referral routes: DB, auth, rate limiters, services.
"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.users.utils.rate_limiter import RateLimiter, get_rate_limiter_dependency
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User


# ─── Rate limiters ─────────────────────────────────────────────────
referral_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
register_rate_limiter = RateLimiter(max_requests=10, window_seconds=3600)
qr_code_rate_limiter = RateLimiter(max_requests=10, window_seconds=3600)


# ─── DB & Auth ─────────────────────────────────────────────────────
def get_db():
    """Dependency for obtaining a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: Session = Depends(get_db),
) -> User:
    """Get authenticated user from JWT token."""
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = payload.get("sub")
        user = db.query(User).filter(
            User.id == user_id,
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
    """Get user if authenticated, None otherwise (no error)."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = payload.get("sub")
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True,
            User.is_deleted == False,
        ).first()
        return user
    except Exception:
        return None


# ─── Rate limiter dependencies ─────────────────────────────────────
def get_rate_limiter_dependency(limiter: RateLimiter):
    """Factory to create a rate limiter FastAPI dependency."""
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep


# ─── Service factories ─────────────────────────────────────────────
def get_referral_service(db: Session = Depends(get_db)):
    """Factory for ReferralService with DB injection."""
    from app.modules.referral.services.referral_service import ReferralService
    return ReferralService(db=db)


def get_analytics_service(db: Session = Depends(get_db)):
    """Factory for ReferralAnalytics with DB injection."""
    from app.modules.referral.services.referral_analytics import ReferralAnalytics
    return ReferralAnalytics(db=db)


def get_qr_service(db: Session = Depends(get_db)):
    """Factory for QRCodeService with DB and Redis injection."""
    from app.modules.referral.services.qr_code_service import QRCodeService
    try:
        from app.modules.core.redis_client import redis_client
        return QRCodeService(cache_redis=redis_client)
    except Exception:
        return QRCodeService()
