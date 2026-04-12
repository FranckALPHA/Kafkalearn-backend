from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import RateLimiter

school_create_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)
school_join_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
school_delete_rate_limiter = RateLimiter(max_requests=1, window_seconds=60)

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
):
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


def get_rate_limiter_dependency(limiter: RateLimiter):
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep


async def forbid_already_in_school(current_user: User = Depends(get_current_user)):
    if current_user.school_id:
        raise HTTPException(status_code=409, detail="ALREADY_IN_SCHOOL")
    return current_user


def require_school_for_user(school_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.modules.school.models import SchoolMember
    membership = db.query(SchoolMember).filter(
        SchoolMember.school_id == school_id,
        SchoolMember.user_id == current_user.id,
        SchoolMember.is_active == True,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="NOT_SCHOOL_MEMBER")
    return current_user


def require_school_admin(school_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.modules.school.models import SchoolMember
    membership = db.query(SchoolMember).filter(
        SchoolMember.school_id == school_id,
        SchoolMember.user_id == current_user.id,
        SchoolMember.role_ecole == "admin",
        SchoolMember.is_active == True,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="NOT_SCHOOL_ADMIN")
    return current_user


def get_school_service(db: Session = Depends(get_db)):
    from app.modules.school.services.school_service import SchoolService
    return SchoolService(db=db)


def get_member_service(db: Session = Depends(get_db)):
    from app.modules.school.services.school_member_service import SchoolMemberService
    return SchoolMemberService(db=db)


def get_quota_service(db: Session = Depends(get_db)):
    from app.modules.school.services.school_quota_service import SchoolQuotaService
    return SchoolQuotaService(db=db)


def get_engagement_service(db: Session = Depends(get_db)):
    from app.modules.school.services.school_engagement_service import SchoolEngagementService
    return SchoolEngagementService(db=db)


def get_expiration_service(db: Session = Depends(get_db)):
    from app.modules.school.services.school_expiration_service import SchoolExpirationService
    return SchoolExpirationService(db=db)
