from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import RateLimiter

daily_quiz_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
daily_quiz_submit_rate_limiter = RateLimiter(max_requests=3, window_seconds=600)

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


def get_quiz_generator(db: Session = Depends(get_db)):
    from app.modules.daily_quiz.services.daily_quiz_generator import DailyQuizGeneratorService
    return DailyQuizGeneratorService(db=db)


def get_correction_service(db: Session = Depends(get_db)):
    from app.modules.daily_quiz.services.daily_quiz_correction import DailyQuizCorrectionService
    return DailyQuizCorrectionService(db=db)


def get_leaderboard_service(db: Session = Depends(get_db)):
    from app.modules.daily_quiz.services.leaderboard_service import LeaderboardService
    return LeaderboardService(db=db)
