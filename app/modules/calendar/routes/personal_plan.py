"""
routes/personal_plan.py
=======================
Endpoints pour les etudes personnelles (en dehors de l'emploi du temps officiel).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.modules.calendar.models import CalendarPersonalStudy
from app.modules.calendar.routes.dependencies import (
    get_db,
    get_current_user,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/personal-plan", tags=["calendar-personal-plan"])


# ─── GET /calendar/personal-plan/ ────────────────────────────────

@router.get("/")
async def list_personal_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste les entrees d'etude personnelle de l'utilisateur."""
    entries = db.query(CalendarPersonalStudy).filter(
        CalendarPersonalStudy.user_id == current_user.id,
        CalendarPersonalStudy.is_active.is_(True),
    ).order_by(CalendarPersonalStudy.day_of_week, CalendarPersonalStudy.start_time).all()

    return {"entries": [e.serialize() for e in entries]}


# ─── POST /calendar/personal-plan/ ───────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_personal_plan_entry(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cree une nouvelle entree d'etude personnelle."""
    from datetime import time

    subject = body.get("subject")
    day_of_week = body.get("day_of_week")
    start_time = body.get("start_time")
    duration_minutes = body.get("duration_minutes")
    priority = body.get("priority", "normal")

    if not all([subject, day_of_week is not None, start_time, duration_minutes]):
        raise HTTPException(status_code=400, detail="Champs requis manquants")

    start = time.fromisoformat(start_time)

    entry = CalendarPersonalStudy(
        user_id=current_user.id,
        subject=subject,
        day_of_week=day_of_week,
        start_time=start,
        duration_minutes=duration_minutes,
        priority=priority,
        is_active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {"entry": entry.serialize(), "message": "Entree d'etude personnelle creee"}


# ─── DELETE /calendar/personal-plan/{entry_id} ───────────────────

@router.delete("/{entry_id}")
async def delete_personal_plan_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime une entree d'etude personnelle."""
    entry = db.query(CalendarPersonalStudy).filter(
        CalendarPersonalStudy.id == entry_id,
        CalendarPersonalStudy.user_id == current_user.id,
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entree introuvable")

    entry.is_active = False
    db.commit()

    return {"message": "Entree d'etude personnelle supprimee"}
