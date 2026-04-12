"""
routes/reports.py
=================
Endpoints pour les rapports de performance et resumes hebdomadaires.
"""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.calendar.schemas.responses import (
    PerformanceReportResponse,
)
from app.modules.calendar.models import CalendarSession
from app.modules.calendar.routes.dependencies import (
    get_db,
    get_current_user,
    get_performance_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["calendar-reports"])


# ─── GET /calendar/reports/performance ───────────────────────────

@router.get("/performance", response_model=PerformanceReportResponse)
async def get_performance_report(
    periode_jours: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    performance_service=Depends(get_performance_service),
):
    """Rapport de performance sur une periode donnee."""
    result = await performance_service.calculer_rapport(
        user_id=str(current_user.id),
        periode_jours=periode_jours,
    )
    return PerformanceReportResponse(
        periode_jours=result["periode_jours"],
        total_sessions=result["total_sessions"],
        total_heures_etude=result["total_heures_etude"],
        avg_concentration=result["avg_concentration"],
        subjects_breakdown=result["subjects_breakdown"],
        streak=result["streak"],
    )


# ─── GET /calendar/reports/weekly-summary ────────────────────────

@router.get("/weekly-summary")
async def get_weekly_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume hebdomadaire: nombre de sessions, heures totales, streak."""
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    sessions = db.query(CalendarSession).filter(
        CalendarSession.user_id == current_user.id,
        CalendarSession.status == "completed",
        CalendarSession.actual_end >= seven_days_ago,
    ).all()

    total_sessions = len(sessions)
    total_hours = sum(s.accumulated_seconds or 0 for s in sessions) / 3600.0

    # Streak
    streak = current_user.streak_jours or 0

    # Sessions par matiere
    subject_counts: dict[str, int] = {}
    for s in sessions:
        if s.subject:
            subject_counts[s.subject] = subject_counts.get(s.subject, 0) + 1

    # Concentration moyenne
    concentrations = [s.concentration_ratio for s in sessions if s.concentration_ratio is not None]
    avg_concentration = (
        round(sum(concentrations) / len(concentrations), 2) if concentrations else 0.0
    )

    # Session la plus recente
    last_session = max(sessions, key=lambda s: s.actual_end) if sessions else None

    return {
        "week_start": seven_days_ago.date().isoformat(),
        "week_end": datetime.now(timezone.utc).date().isoformat(),
        "total_sessions": total_sessions,
        "total_hours": round(total_hours, 2),
        "avg_concentration": avg_concentration,
        "streak": streak,
        "subjects": subject_counts,
        "last_session_date": last_session.actual_end.date().isoformat() if last_session else None,
    }
