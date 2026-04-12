from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import RateLimiter

wisdom_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
share_rate_limiter = RateLimiter(max_requests=3, window_seconds=86400)  # 3/day

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user = db.query(User).filter(User.id == payload.get("sub"), User.is_active == True).first()
        if not user:
            raise HTTPException(status_code=401, detail="USER_NOT_FOUND")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

async def get_current_superadmin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")
    return current_user

def get_rate_limiter_dependency(limiter: RateLimiter):
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep

def get_wisdom_service(db: Session = Depends(get_db)):
    from app.modules.wisdom.services.wisdom_service import WisdomService
    return WisdomService(db=db)

def get_wisdom_analytics_service(db: Session = Depends(get_db)):
    from app.modules.wisdom.services.wisdom_analytics_service import WisdomAnalyticsService
    return WisdomAnalyticsService(db=db)
