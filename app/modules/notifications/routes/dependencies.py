"""
routes/dependencies.py
======================
FastAPI dependencies for the notifications module.
"""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.users.utils.rate_limiter import RateLimiter, get_rate_limiter_dependency
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import HTTPException, status

# ─── Rate limiters ──────────────────────────────────────────────────
notif_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
register_rate_limiter = RateLimiter(max_requests=10, window_seconds=3600)  # 10/hour

security = HTTPBearer()


def get_db():
    """Dependency to get a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Retrieve authenticated user via JWT."""
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = payload.get("sub")
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True,  # noqa: E712
            User.is_deleted == False,  # noqa: E712
        ).first()
        if not user:
            raise HTTPException(status_code=401, detail="USER_NOT_FOUND")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the user is an admin.
    
    NOTE: Disabled for development phase - any user can access admin routes.
    """
    # DEV MODE: Allow any authenticated user
    return current_user
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")
    return current_user


def get_rate_limiter_dependency(limiter: RateLimiter):
    """Factory to create a FastAPI rate-limiting dependency."""
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep


def get_notification_service(db: Session = Depends(get_db)):
    """Factory for NotificationService."""
    from app.modules.notifications.services.notification_service import NotificationService
    return NotificationService(db=db)


def get_scheduler_service(db: Session = Depends(get_db)):
    """Factory for NotificationScheduler."""
    from app.modules.notifications.services.notification_scheduler import NotificationScheduler
    return NotificationScheduler(db=db)


def get_analytics_service(db: Session = Depends(get_db)):
    """Factory for NotificationAnalytics."""
    from app.modules.notifications.services.notification_analytics import NotificationAnalytics
    return NotificationAnalytics(db=db)
