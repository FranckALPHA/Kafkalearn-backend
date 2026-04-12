"""
routes/dependencies.py
======================
Dependencies FastAPI pour le module calendar: rate limiters, DB, auth, services.
"""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.users.routes.dependencies import get_current_user, get_db as users_get_db
from app.modules.users.utils.rate_limiter import RateLimiter, get_rate_limiter_dependency
from app.modules.users.models import User

# ─── Rate limiters ────────────────────────────────────────────────

calendar_sessions_rate = RateLimiter(max_requests=60, window_seconds=60)
calendar_create_rate = RateLimiter(max_requests=10, window_seconds=60)
calendar_ping_rate = RateLimiter(max_requests=10, window_seconds=60)
calendar_suggestions_rate = RateLimiter(max_requests=30, window_seconds=60)


# ─── DB ───────────────────────────────────────────────────────────

def get_db():
    """Yield a SQLAlchemy session, mirroring the users module pattern."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Rate limiter wrappers ────────────────────────────────────────

def get_rate_limiter_sessions(request: Request):
    return get_rate_limiter_dependency(calendar_sessions_rate)


def get_rate_limiter_create(request: Request):
    return get_rate_limiter_dependency(calendar_create_rate)


def get_rate_limiter_ping(request: Request):
    return get_rate_limiter_dependency(calendar_ping_rate)


def get_rate_limiter_suggestions(request: Request):
    return get_rate_limiter_dependency(calendar_suggestions_rate)


# ─── Service factories ────────────────────────────────────────────

def get_session_state_service(db: Session = Depends(get_db)):
    from app.modules.calendar.services.session_state_service import SessionStateService
    return SessionStateService(db=db)


def get_content_suggestion_service(db: Session = Depends(get_db)):
    from app.modules.calendar.services.content_suggestion_service import ContentSuggestionService
    return ContentSuggestionService(db=db)


def get_coach_service(db: Session = Depends(get_db)):
    from app.modules.calendar.services.study_coach_service import StudyCoachService
    return StudyCoachService(db=db)


def get_performance_service(db: Session = Depends(get_db)):
    from app.modules.calendar.services.performance_report_service import PerformanceReportService
    return PerformanceReportService(db=db)
