import logging
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.modules.daily_quiz.routes.dependencies import (
    get_db,
    get_current_user,
    get_leaderboard_service,
    get_rate_limiter_dependency,
    daily_quiz_rate_limiter,
)
from app.modules.daily_quiz.schemas.responses import LeaderboardResponse
from app.modules.users.models import User
from app.modules.daily_quiz.models import MonthlyLeaderboard
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/daily-quiz/leaderboard", tags=["daily-quiz-leaderboard"])


@router.get("/", response_model=LeaderboardResponse)
async def get_leaderboard(
    month_year: str = Query(None, description="Month in YYYY-MM format. Defaults to current month."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rate_limiter_dependency(daily_quiz_rate_limiter)),
):
    """Get monthly leaderboard with user's rank."""
    if month_year is None:
        month_year = datetime.now().strftime("%Y-%m")

    leaderboard_svc = get_leaderboard_service(db=db)
    result = await leaderboard_svc.obtenir_leaderboard(
        month_year=month_year,
        limit=20,
        user_id=current_user.id,
    )

    # Get total participants
    total = (
        db.query(func.count(MonthlyLeaderboard.id))
        .filter(MonthlyLeaderboard.month_year == month_year)
        .scalar()
    )

    mon_rang = None
    if result.get("current_user_rank"):
        user_entry = (
            db.query(MonthlyLeaderboard)
            .filter(
                MonthlyLeaderboard.user_id == current_user.id,
                MonthlyLeaderboard.month_year == month_year,
            )
            .first()
        )
        if user_entry:
            mon_rang = {
                "rang": result["current_user_rank"],
                "total_score": user_entry.total_score,
                "nb_participations": user_entry.nb_participations,
                "meilleur_score_pct": user_entry.meilleur_score_pct,
            }

    return LeaderboardResponse(
        month_year=month_year,
        top_entries=result.get("top_entries", []),
        mon_rang=mon_rang,
        total_participants=total or 0,
    )
