import logging
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.modules.daily_quiz.routes.dependencies import (
    get_db,
    get_current_user,
    get_quiz_generator,
    get_rate_limiter_dependency,
    daily_quiz_rate_limiter,
)
from app.modules.users.models import User
from app.modules.daily_quiz.models import DailyQuiz, DailyQuizAttempt
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/daily-quiz", tags=["admin-daily-quiz"])


def _require_superadmin(user: User):
    """Ensure the current user is a SuperAdmin."""
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SUPERADMIN_REQUIRED")


@router.get("/stats")
async def get_global_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rate_limiter_dependency(daily_quiz_rate_limiter)),
):
    """Global quiz statistics (SuperAdmin only)."""
    _require_superadmin(current_user)

    total_quizzes = db.query(func.count(DailyQuiz.id)).scalar()
    total_attempts = db.query(func.count(DailyQuizAttempt.id)).scalar()
    avg_score_row = db.query(func.avg(DailyQuizAttempt.score_pourcentage)).first()
    avg_score = float(avg_score_row[0]) if avg_score_row and avg_score_row[0] is not None else 0.0

    today = date.today()
    today_quiz = db.query(DailyQuiz).filter(DailyQuiz.quiz_date == today).first()
    today_attempts = 0
    if today_quiz:
        today_attempts = (
            db.query(func.count(DailyQuizAttempt.id))
            .filter(DailyQuizAttempt.daily_quiz_id == today_quiz.id)
            .scalar()
        )

    return {
        "total_quizzes": total_quizzes or 0,
        "total_attempts": total_attempts or 0,
        "average_score": round(avg_score, 2),
        "today_quiz": {
            "exists": today_quiz is not None,
            "attempts": today_attempts,
            "theme": today_quiz.theme if today_quiz else None,
        },
    }


@router.post("/generate/{date_str}")
async def force_generate_quiz(
    date_str: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force quiz generation for a specific date (SuperAdmin only)."""
    _require_superadmin(current_user)

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="INVALID_DATE_FORMAT")

    generator = get_quiz_generator(db=db)
    try:
        result = await generator.generer_quiz_du_jour(date_cible=target_date, force=True)
    except Exception as exc:
        logger.error("Failed to generate quiz for %s: %s", date_str, exc)
        raise HTTPException(status_code=500, detail=f"GENERATION_FAILED: {exc}")

    return {
        "status": "ok",
        "date": str(target_date),
        "quiz": result,
    }
