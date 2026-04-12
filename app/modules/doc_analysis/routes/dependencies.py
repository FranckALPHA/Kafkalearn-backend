from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import RateLimiter

analyze_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
feedback_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

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


def get_rate_limiter_dependency(limiter: RateLimiter):
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep


def get_analysis_service(db: Session = Depends(get_db)):
    from app.modules.doc_analysis.services.document_analysis_service import DocumentAnalysisService
    return DocumentAnalysisService(db=db)


def get_feedback_service(db: Session = Depends(get_db)):
    from app.modules.doc_analysis.services.analysis_feedback_service import AnalysisFeedbackService
    return AnalysisFeedbackService(db=db)


def get_cache_service(db: Session = Depends(get_db)):
    from app.modules.doc_analysis.services.analysis_cache_service import AnalysisCacheService
    return AnalysisCacheService(db=db)
