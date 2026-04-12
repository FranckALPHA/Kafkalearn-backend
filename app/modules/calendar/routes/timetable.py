"""
routes/timetable.py
===================
Endpoints pour l'emploi du temps hebdomadaire.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.modules.calendar.schemas.requests import TimetableEntryRequest
from app.modules.calendar.models import CalendarTimetable
from app.modules.calendar.routes.dependencies import (
    get_db,
    get_current_user,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timetable", tags=["calendar-timetable"])


# ─── GET /calendar/timetable/ ────────────────────────────────────

@router.get("/")
async def list_timetable(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste les entrees de l'emploi du temps de l'utilisateur."""
    entries = db.query(CalendarTimetable).filter(
        CalendarTimetable.user_id == current_user.id,
        CalendarTimetable.is_active.is_(True),
    ).order_by(CalendarTimetable.day_of_week, CalendarTimetable.start_time).all()

    return {"entries": [e.serialize() for e in entries]}


# ─── POST /calendar/timetable/ ───────────────────────────────────

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_timetable_entry(
    body: TimetableEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cree une nouvelle entree dans l'emploi du temps."""
    from datetime import time

    start = time.fromisoformat(body.start_time)
    end = time.fromisoformat(body.end_time)

    entry = CalendarTimetable(
        user_id=current_user.id,
        subject=body.subject,
        day_of_week=body.day_of_week,
        start_time=start,
        end_time=end,
        is_active=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {"entry": entry.serialize(), "message": "Entree d'emploi du temps creee"}


# ─── DELETE /calendar/timetable/{entry_id} ───────────────────────

@router.delete("/{entry_id}")
async def delete_timetable_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime une entree de l'emploi du temps."""
    entry = db.query(CalendarTimetable).filter(
        CalendarTimetable.id == entry_id,
        CalendarTimetable.user_id == current_user.id,
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entree introuvable")

    entry.is_active = False
    db.commit()

    return {"message": "Entree d'emploi du temps supprimee"}
