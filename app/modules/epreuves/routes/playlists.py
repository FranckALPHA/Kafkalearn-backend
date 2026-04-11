import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.epreuves.schemas.requests import PlaylistCreateRequest, PlaylistAddDocumentRequest
from app.modules.epreuves.schemas.responses import PlaylistResponse, PlaylistListResponse
from app.modules.epreuves.routes.dependencies import (
    get_db, get_current_user, get_playlist_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epreuves/playlists", tags=["Epreuves - Playlists"])


@router.get("/", response_model=PlaylistListResponse)
async def list_playlists(
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    playlists = await playlist_service.lister_playlists(str(current_user.id))
    return {"playlists": playlists, "total": len(playlists)}


@router.post("/", response_model=dict)
async def create_playlist(
    payload: PlaylistCreateRequest,
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    result = await playlist_service.creer_playlist(
        user_id=str(current_user.id),
        nom=payload.nom,
        description=payload.description,
        objectif=payload.objectif,
    )
    return result


@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(
    playlist_id: int,
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    result = await playlist_service.obtenir_playlist(playlist_id, str(current_user.id))
    return PlaylistResponse(**result)


@router.post("/{playlist_id}/documents")
async def add_document_to_playlist(
    playlist_id: int,
    payload: PlaylistAddDocumentRequest,
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    result = await playlist_service.ajouter_document(
        playlist_id=playlist_id,
        document_id=payload.document_id,
        user_id=str(current_user.id),
    )
    return result


@router.delete("/{playlist_id}/documents/{document_id}")
async def remove_document_from_playlist(
    playlist_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    result = await playlist_service.supprimer_document(
        playlist_id=playlist_id,
        document_id=document_id,
        user_id=str(current_user.id),
    )
    return result


@router.post("/{playlist_id}/share")
async def share_playlist(
    playlist_id: int,
    is_public: bool = True,
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    result = await playlist_service.partager_playlist(
        playlist_id=playlist_id,
        user_id=str(current_user.id),
        is_public=is_public,
    )
    return result


@router.post("/copy/{playlist_id_source}")
async def copy_public_playlist(
    playlist_id_source: int,
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    result = await playlist_service.copier_playlist_publique(
        playlist_id_source=playlist_id_source,
        user_id=str(current_user.id),
    )
    return result


@router.delete("/{playlist_id}")
async def delete_playlist(
    playlist_id: int,
    current_user: User = Depends(get_current_user),
    playlist_service=Depends(get_playlist_service),
):
    result = await playlist_service.supprimer_playlist(
        playlist_id=playlist_id,
        user_id=str(current_user.id),
    )
    return result
