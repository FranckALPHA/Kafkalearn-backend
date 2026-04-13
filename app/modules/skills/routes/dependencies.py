"""
routes/dependencies.py
======================
Dépendances FastAPI pour le module skills.
"""
from fastapi import Depends, Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.users.utils.security import decode_token
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import RateLimiter

# Rate limiters pour skills
skills_run_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
skills_list_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)
skills_detect_rate_limiter = RateLimiter(max_requests=15, window_seconds=60)
chat_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

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
) -> User:
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user = db.query(User).filter(
            User.id == payload.get("sub"),
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


def get_rate_limiter_dependency(limiter: RateLimiter):
    """Factory pour créer une dépendance FastAPI de rate limiting."""
    async def rate_limit_dep(request: Request):
        await limiter(request)
        return True
    return rate_limit_dep


def get_skill_dispatcher(db: Session = Depends(get_db)):
    from app.modules.skills.services.skill_dispatcher import SkillDispatcher
    from app.modules.skills.utils.llm_client import LLMClient
    from app.core.config import OPENROUTER_API_KEYS

    llm_client = LLMClient(
        api_keys={
            "openrouter_api_keys": OPENROUTER_API_KEYS,
        }
    )
    return SkillDispatcher(db=db, llm_client=llm_client)


def get_idempotency_service():
    from app.modules.skills.services.idempotency_service import IdempotencyService
    return IdempotencyService()


def get_quiz_correction_service(db: Session = Depends(get_db)):
    from app.modules.skills.services.quiz_correction_service import QuizCorrectionService
    return QuizCorrectionService(db=db)


def get_chat_service(db: Session = Depends(get_db)):
    from app.modules.skills.services.chat_service import ChatService
    return ChatService(db=db)


def get_analytics_service(db: Session = Depends(get_db)):
    from app.modules.skills.services.skill_analytics_service import SkillAnalyticsService
    return SkillAnalyticsService(db=db)


def get_skill_recommender_service(db: Session = Depends(get_db)):
    from app.modules.skills.services.skill_recommender_service import SkillRecommenderService
    return SkillRecommenderService(db=db)
