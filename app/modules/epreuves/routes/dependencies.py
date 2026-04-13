from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import RateLimiter

epreuves_rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
download_rate_limiter = RateLimiter(max_requests=20, window_seconds=3600)

security = HTTPBearer()

PLAN_HIERARCHY = ['freemium', 'access', 'premium', 'pro', 'unlimited', 'school']

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
        return db.query(User).filter(User.id == payload.get("sub"), User.is_active == True).first()
    except Exception:
        return None

def require_can_download(current_user: User = Depends(get_current_user)):
    """Check if user can download.
    
    NOTE: Disabled for development phase - everyone can download.
    """
    # DEV MODE: Always allow
    return current_user
    if PLAN_HIERARCHY.index(current_user.plan_effectif) < PLAN_HIERARCHY.index("access"):
        raise HTTPException(status_code=403, detail="PLAN_INSUFFISANT")
    return current_user

def get_rate_limiter_dependency(limiter: RateLimiter):
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep

def get_document_service(db: Session = Depends(get_db)):
    from app.modules.epreuves.services.document_service import DocumentService
    return DocumentService(db=db)

def get_playlist_service(db: Session = Depends(get_db)):
    from app.modules.epreuves.services.playlist_service import PlaylistService
    return PlaylistService(db=db)

def get_stats_service(db: Session = Depends(get_db)):
    from app.modules.epreuves.services.document_stats_service import DocumentStatsService
    return DocumentStatsService(db=db)

def get_filter_cache_service(db: Session = Depends(get_db)):
    from app.modules.epreuves.services.filter_cache_service import FilterCacheService
    return FilterCacheService(db=db)

def get_recommendation_engine(db: Session = Depends(get_db)):
    from app.modules.epreuves.services.recommendation_engine import RecommendationEngine
    return RecommendationEngine(db=db)
