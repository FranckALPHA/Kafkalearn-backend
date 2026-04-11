"""
routes/chat.py
==============
Gestion des sessions et messages de chat.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.skills.routes.dependencies import (
    get_db,
    get_current_user,
    get_rate_limiter_dependency,
    chat_rate_limiter,
    get_chat_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills/chat", tags=["Skills - Chat"])


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Liste les sessions de chat de l'utilisateur."""
    sessions = chat_service.get_user_sessions(
        user_id=str(current_user.id),
        limit=limit,
        offset=offset,
    )
    return {"sessions": sessions, "total": len(sessions)}


@router.post("/sessions")
async def create_session(
    titre: str = Query("Nouvelle session", min_length=1, max_length=255),
    matiere: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Crée une nouvelle session de chat."""
    session = await chat_service.creer_session(
        user_id=str(current_user.id),
        titre=titre,
        matiere=matiere,
    )
    return {"session_id": str(session.id), "titre": session.titre}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Récupère les détails d'une session."""
    session = chat_service.get_session(session_id, str(current_user.id))
    if not session:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return session.serialize_list_item()


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Récupère les messages d'une session."""
    # Vérifier ownership
    session = chat_service.get_session(session_id, str(current_user.id))
    if not session:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

    messages = chat_service.get_messages(session_id, limit=limit)
    return {"messages": messages, "total": len(messages)}


@router.put("/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    titre: str = Query(..., min_length=1, max_length=255),
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Met à jour le titre d'une session."""
    success = chat_service.update_session_title(session_id, str(current_user.id), titre)
    if not success:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return {"message": "Titre mis à jour"}


@router.post("/sessions/{session_id}/pin")
async def pin_session(
    session_id: str,
    pinned: bool = True,
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Épingle ou désépingle une session."""
    success = chat_service.pin_session(session_id, str(current_user.id), pinned)
    if not success:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return {"message": "Session épinglée" if pinned else "Session désépinglée"}


@router.post("/sessions/{session_id}/archive")
async def archive_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Archive une session."""
    success = chat_service.archive_session(session_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return {"message": "Session archivée"}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    chat_service=Depends(get_chat_service),
):
    """Supprime définitivement une session."""
    success = chat_service.delete_session(session_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    return {"message": "Session supprimée"}
