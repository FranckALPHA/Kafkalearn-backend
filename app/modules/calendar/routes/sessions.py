"""
routes/sessions.py
==================
Endpoints pour la gestion des sessions d'etude du calendrier.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.modules.calendar.schemas.requests import (
    SessionCreateRequest,
    PingRequest,
    SessionStatusUpdateRequest,
    SessionUpdateRequest,
)
from app.modules.calendar.schemas.responses import (
    SessionResponse,
    SessionListResponse,
    SuggestionsResponse,
    HeatmapResponse,
    CoachInsightsResponse,
)
from app.modules.calendar.models.calendar_session import CalendarSession
from app.modules.calendar.routes.dependencies import (
    get_db,
    get_current_user,
    get_rate_limiter_sessions,
    get_rate_limiter_create,
    get_rate_limiter_ping,
    get_rate_limiter_suggestions,
    get_session_state_service,
    get_content_suggestion_service,
    get_coach_service,
    get_performance_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calendar-sessions"])


# ─── GET /calendar/sessions ──────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    date_debut: str | None = Query(None),
    date_fin: str | None = Query(None),
    status: str | None = Query(None),
    subject: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(get_rate_limiter_sessions),
    session_state_service=Depends(get_session_state_service),
):
    """Liste les sessions avec filtres et pagination."""
    await session_state_service.synchroniser_etats(str(current_user.id))

    query = db.query(CalendarSession).filter(
        CalendarSession.user_id == current_user.id,
        CalendarSession.is_deleted == False,
    )

    if date_debut:
        query = query.filter(CalendarSession.planned_start >= normaliser_date(date_debut))
    if date_fin:
        query = query.filter(CalendarSession.planned_start <= normaliser_date(date_fin))
    if status:
        query = query.filter(CalendarSession.status == status)

    if subject:
        query = query.filter(CalendarSession.subject == subject)

    total = query.count()
    offset = (page - 1) * limit
    sessions = query.order_by(CalendarSession.planned_start.desc()).offset(offset).limit(limit).all()

    return SessionListResponse(
        total=total,
        page=page,
        limit=limit,
        sessions=[s.serialize_for_list() for s in sessions],
    )


# ─── POST /calendar/sessions ─────────────────────────────────────

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(get_rate_limiter_create),
):
    """Cree une nouvelle session d'etude."""
    from datetime import timedelta

    planned_start = datetime.fromisoformat(body.planned_start)
    planned_end = planned_start + timedelta(minutes=body.planned_duration_minutes)

    session = CalendarSession(
        user_id=current_user.id,
        subject=body.subject,
        titre=body.titre,
        planned_start=planned_start,
        planned_end=planned_end,
        planned_duration_minutes=body.planned_duration_minutes,
        ressource_principale_id=body.ressource_principale_id,
        ressource_principale_type=body.ressource_principale_type,
        is_ai_generated=body.is_ai_generated,
        humeur_debut=body.humeur_debut,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Ressources suggerees
    suggested_resources = []
    if session.ressource_principale_id:
        suggested_resources.append({
            "id": session.ressource_principale_id,
            "type": session.ressource_principale_type,
        })

    return SessionResponse(**session.serialize_detail())


# ─── POST /calendar/sessions/{session_id}/ping ───────────────────

@router.post("/sessions/{session_id}/ping", response_model=SessionResponse)
async def ping_session(
    session_id: int,
    body: PingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(get_rate_limiter_ping),
    session_state_service=Depends(get_session_state_service),
):
    """Envoie un ping pour une session active."""
    try:
        result = await session_state_service.traiter_ping(
            session_id=session_id,
            user_id=str(current_user.id),
            elapsed_client=body.elapsed_client,
        )
        return SessionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ─── PATCH /calendar/sessions/{session_id} ───────────────────────

@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: int,
    body: SessionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_state_service=Depends(get_session_state_service),
):
    """Met a jour les details d'une session (subject, titre, etc.)."""
    try:
        # On ne transmet que les champs fournis (exclude_unset=True)
        update_data = body.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

        result = await session_state_service.update_session(
            session_id=session_id,
            user_id=str(current_user.id),
            data=update_data,
        )
        return SessionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── PATCH /calendar/sessions/{session_id}/status ────────────────

@router.patch("/sessions/{session_id}/status", response_model=SessionResponse)
async def update_session_status(
    session_id: int,
    body: SessionStatusUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_state_service=Depends(get_session_state_service),
):
    """Met a jour le statut d'une session (completed/failed/cancelled)."""
    session = db.query(CalendarSession).filter(
        CalendarSession.id == session_id,
        CalendarSession.user_id == current_user.id,
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    valid_statuses = ("completed", "failed", "cancelled", "planned", "active", "paused", "skipped")
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status invalide. Attendu: {valid_statuses}")

    if body.status == "completed":
        result = await session_state_service.completer_session(
            session_id=session_id,
            user_id=str(current_user.id),
            humeur_fin=body.humeur_fin,
            note_session=body.note_session,
        )

        # Background: enrichir les signaux temporels (Coach IA)
        background_tasks.add_task(
            _enrich_temporal_signals,
            user_id=str(current_user.id),
            matiere=session.subject,
            duration_min=session.accumulated_seconds // 60 if session.accumulated_seconds else 30,
            completed=True,
        )

        return SessionResponse(**result)

    session.status = body.status
    if body.humeur_fin:
        session.humeur_fin = body.humeur_fin
    if body.note_session:
        session.note_session = body.note_session
    db.commit()
    db.refresh(session)

    return SessionResponse(**session.serialize_detail())


# ─── GET /calendar/suggestions ───────────────────────────────────

@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(
    date: str | None = Query(None, description="ISO date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _=Depends(get_rate_limiter_suggestions),
    content_suggestion_service=Depends(get_content_suggestion_service),
):
    """Recupere les suggestions d'etude pour une date."""
    from datetime import datetime as dt

    target_date = dt.fromisoformat(date) if date else dt.now(timezone.utc)
    result = await content_suggestion_service.obtenir_suggestions_cached(
        user_id=str(current_user.id),
        target_date=target_date,
    )

    suggestions_data = result.get("suggestions", {})
    if isinstance(suggestions_data, dict):
        suggestions_list = []
        for category, items in suggestions_data.items():
            if isinstance(items, list):
                suggestions_list.extend(items)
    else:
        suggestions_list = suggestions_data if isinstance(suggestions_data, list) else []

    return SuggestionsResponse(
        date=result.get("date", target_date.date().isoformat()),
        matieres_du_jour=result.get("matieres_du_jour", []),
        suggestions=suggestions_list,
        cached=result.get("source") in ("redis", "db"),
        generated_at=result.get("generated_at"),
    )


# ─── GET /calendar/coach-insights ────────────────────────────────

@router.get("/coach-insights", response_model=CoachInsightsResponse)
async def get_coach_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    coach_service=Depends(get_coach_service),
):
    """Recupere les insights personnalises du coach."""
    insights = await coach_service.generer_insights(user_id=str(current_user.id))
    return CoachInsightsResponse(
        insights=insights,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ─── GET /calendar/heatmap ───────────────────────────────────────

@router.get("/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    nb_jours: int = Query(365, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    performance_service=Depends(get_performance_service),
):
    """Recupere les donnees de la heatmap d'activite."""
    result = await performance_service.calculer_heatmap(
        user_id=str(current_user.id),
        nb_jours=nb_jours,
    )
    return HeatmapResponse(
        data=result["data"],
        total=result["total"],
        max_count=result["max_count"],
    )


# ────────────────────────────────────────────────────────────────
# Background enrichment (post-response, non bloquant)
# ────────────────────────────────────────────────────────────────

def _enrich_temporal_signals(user_id: str, matiere: str, duration_min: int, completed: bool):
    """Enrichit les signaux temporels après une session calendar complétée."""
    try:
        from app.core.database import SessionLocal
        from app.modules.users.services.coach_service import CoachService

        db = SessionLocal()
        coach = CoachService(db)
        coach.record_session(
            user_id=user_id,
            duration_min=duration_min,
            matiere=matiere or "general",
            score=80 if completed else 30,  # estimation
            difficulty="medium",
            completed=completed,
        )
        db.close()
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to enrich temporal signals: {e}")
