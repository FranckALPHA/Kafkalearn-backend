import logging
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.daily_quiz.routes.dependencies import (
    get_db,
    get_current_user,
    get_correction_service,
    get_quiz_generator,
    get_rate_limiter_dependency,
    daily_quiz_rate_limiter,
    daily_quiz_submit_rate_limiter,
)
from app.modules.daily_quiz.schemas.requests import SubmitAnswerRequest
from app.modules.daily_quiz.schemas.responses import QuizResponse, SubmitResultResponse
from app.modules.daily_quiz.models import DailyQuiz, DailyQuizAttempt
from app.modules.users.models import User
from app.modules.daily_quiz.services.quiz_streak_service import QuizStreakService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daily-quiz", tags=["daily-quiz"])


@router.get("/today", response_model=QuizResponse)
async def get_todays_quiz(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rate_limiter_dependency(daily_quiz_rate_limiter)),
):
    """Get today's quiz. Returns questions without answers if not yet attempted,
    or with answers revealed if already attempted."""
    today = date.today()
    quiz = db.query(DailyQuiz).filter(DailyQuiz.quiz_date == today).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="NO_QUIZ_AVAILABLE")

    # Check if user already attempted
    existing_attempt = (
        db.query(DailyQuizAttempt)
        .filter(
            DailyQuizAttempt.user_id == current_user.id,
            DailyQuizAttempt.daily_quiz_id == quiz.id,
        )
        .first()
    )

    deja_tente = existing_attempt is not None
    langue = getattr(current_user, "langue", "fr")
    quiz_data = quiz.serialize_public(langue=langue)

    ma_tentative = None
    if deja_tente:
        ma_tentative = existing_attempt.serialize_result()

    # Calculate remaining time until end of day
    now = datetime.now()
    end_of_day = datetime.combine(today, datetime.max.time())
    temps_restant = int((end_of_day - now).total_seconds())

    return QuizResponse(
        quiz=quiz_data,
        deja_tente=deja_tente,
        ma_tentative=ma_tentative,
        temps_restant_secondes=temps_restant,
    )


@router.post("/today/submit", response_model=SubmitResultResponse)
async def submit_quiz_answer(
    body: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rate_limiter_dependency(daily_quiz_submit_rate_limiter)),
):
    """Submit answers for today's quiz. Corrects and updates leaderboard."""
    today = date.today()
    quiz = db.query(DailyQuiz).filter(DailyQuiz.quiz_date == today).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="NO_QUIZ_AVAILABLE")

    # Check if already submitted
    existing_attempt = (
        db.query(DailyQuizAttempt)
        .filter(
            DailyQuizAttempt.user_id == current_user.id,
            DailyQuizAttempt.daily_quiz_id == quiz.id,
        )
        .first()
    )
    if existing_attempt:
        raise HTTPException(status_code=409, detail="DEJA_TENTE")

    correction_svc = get_correction_service(db=db)
    langue = getattr(current_user, "langue", "fr")

    try:
        result = await correction_svc.corriger_tentative(
            user_id=current_user.id,
            quiz_id=quiz.id,
            reponses_user=body.reponses,
            duree_secondes=body.duree_secondes or 0,
            langue=langue,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.commit()
    return SubmitResultResponse(**result)


@router.get("/stats")
async def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rate_limiter_dependency(daily_quiz_rate_limiter)),
):
    """Get user's quiz statistics: participation count, avg score, streak."""
    participation_count = (
        db.query(func.count(DailyQuizAttempt.id))
        .filter(DailyQuizAttempt.user_id == current_user.id)
        .scalar()
    )

    avg_score_row = (
        db.query(func.avg(DailyQuizAttempt.score_pourcentage))
        .filter(DailyQuizAttempt.user_id == current_user.id)
        .first()
    )
    avg_score = float(avg_score_row[0]) if avg_score_row and avg_score_row[0] is not None else 0.0

    streak_svc = QuizStreakService(db, None)
    streak_info = await streak_svc.get_streak_info(current_user.id)

    return {
        "participation_count": participation_count or 0,
        "average_score": round(avg_score, 2),
        "current_streak": streak_info.get("current_streak", 0),
        "longest_streak": streak_info.get("longest_streak", 0),
        "last_attempt_date": streak_info.get("last_attempt_date"),
    }
