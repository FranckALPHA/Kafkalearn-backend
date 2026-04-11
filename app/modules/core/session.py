"""
modules/core/session.py
=======================
Gestion de session et dépendances FastAPI.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.modules.core.database import get_db
from app.modules.core.security import decode_token
from app.modules.core.config import settings
from app.modules.core.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Dépendance principale pour extraire l'utilisateur authentifié."""
    try:
        payload = decode_token(credentials.credentials, settings.SECRET_KEY, "access")
        user_id = payload.get("sub")

        # Check blacklist
        jti = payload.get("jti")
        if jti and redis_client.exists(f"blacklist:{jti}"):
            raise HTTPException(status_code=401, detail="Token revoked")

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    from app.modules.users.models import User

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
):
    """Retourne l'utilisateur si authentifié, sinon None."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials, settings.SECRET_KEY, "access")
        user_id = payload.get("sub")
        from app.modules.users.models import User
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
    except Exception:
        return None
