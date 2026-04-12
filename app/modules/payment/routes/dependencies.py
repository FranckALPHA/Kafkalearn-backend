"""
routes/dependencies.py
======================
Dependances FastAPI pour le module payment (auth, DB, rate limit, services).
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.users.utils.rate_limiter import RateLimiter, get_rate_limiter_dependency
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User

security = HTTPBearer()

# ─── Rate limiters ─────────────────────────────────────────────

payment_checkout_rate_limiter = RateLimiter(max_requests=3, window_seconds=600)
payment_history_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)


# ─── DB & Auth ─────────────────────────────────────────────────

def get_db():
    """Dependance pour obtenir une session DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Recupere l'utilisateur connecte via JWT."""
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
    """Recupere l'utilisateur si authentifie, sinon None (pas d'erreur)."""
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


async def require_email_verified(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verifie que l'utilisateur a valide son email."""
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EMAIL_NOT_VERIFIED",
        )
    return current_user


# ─── Rate limiter dependencies ────────────────────────────────

def get_rate_limiter_dependency(limiter: RateLimiter):
    """Factory pour creer une dependance FastAPI de rate limiting."""
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep


def get_payment_checkout_rate_limiter(request: Request):
    """Rate limiter pour le checkout payment (3/10min)."""
    return get_rate_limiter_dependency(payment_checkout_rate_limiter)


def get_payment_history_rate_limiter_dep(request: Request):
    """Rate limiter pour l'historique payment (20/min)."""
    return get_rate_limiter_dependency(payment_history_rate_limiter)


# ─── Service factories ────────────────────────────────────────

def get_payment_service(db: Session = Depends(get_db)):
    """Factory pour PaymentService avec injection DB."""
    from app.modules.payment.services import PaymentService
    return PaymentService(db=db)


def get_webhook_service(db: Session = Depends(get_db)):
    """Factory pour WebhookService avec injection DB."""
    from app.modules.payment.services import WebhookService
    return WebhookService(db=db)


def get_analytics_service(db: Session = Depends(get_db)):
    """Factory pour PaymentAnalyticsService avec injection DB."""
    from app.modules.payment.services import PaymentAnalyticsService
    return PaymentAnalyticsService(db=db)
