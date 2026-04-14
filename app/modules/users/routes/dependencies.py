"""
routes/dependencies.py
======================
Dépendances FastAPI réutilisables (auth, DB, rate limit).
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import SessionLocal

from app.modules.users.utils.rate_limiter import (
    auth_rate_limiter,
    register_rate_limiter,
    get_rate_limiter_dependency,
)
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User

security = HTTPBearer()


def get_db():
    """Dépendance pour obtenir une session DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_rate_limiter_register(request: Request):
    """Rate limiter pour l'inscription (3/min)."""
    return get_rate_limiter_dependency(register_rate_limiter)


def get_rate_limiter_auth(request: Request):
    """Rate limiter pour login/verify (5/min)."""
    return get_rate_limiter_dependency(auth_rate_limiter)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Récupère l'utilisateur connecté via JWT."""
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
    """Récupère l'utilisateur si authentifié, sinon None (pas d'erreur)."""
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


async def get_current_superadmin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Vérifie que l'utilisateur est superadmin.
    """
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")
    return current_user


def get_user_service(db: Session = Depends(get_db)):
    """Factory pour UserService avec injection DB."""
    from app.modules.users.services.user_service import UserService
    return UserService(db=db)


def get_learning_profile_service(db: Session = Depends(get_db)):
    """Factory pour LearningProfileService."""
    from app.modules.users.services.learning_profile_service import LearningProfileService
    return LearningProfileService(db=db)


def get_streak_service(db: Session = Depends(get_db)):
    """Factory pour StreakService."""
    from app.modules.users.services.streak_service import StreakService
    return StreakService(db=db)


def get_audit_service(db: Session = Depends(get_db)):
    """Factory pour AuditService."""
    from app.modules.users.services.audit_service import AuditService
    return AuditService(db=db)
