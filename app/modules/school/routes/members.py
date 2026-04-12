"""
routes/members.py
=================
Gestion des membres d'école + import CSV.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.modules.school.schemas.responses import MemberListResponse, SchoolInvitationResult
from app.modules.school.routes.dependencies import (
    get_current_user,
    get_db,
    require_school_admin,
    get_member_service,
)
from app.modules.school.utils.csv_parser import CSVParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/school/members", tags=["School Members"])


@router.get("/", response_model=MemberListResponse)
async def list_members(
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    member_service=Depends(get_member_service),
):
    """Lister les membres de l'école (admin uniquement, avec pagination et recherche)."""
    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    # Verify admin
    require_school_admin(school_id=current_user.school_id, current_user=current_user, db=db)

    result = await member_service.lister_membres(
        school_id=current_user.school_id,
        is_admin=True,
        page=page,
        limit=limit,
        search=search,
    )
    return result


@router.post("/import-csv", response_model=SchoolInvitationResult)
async def import_csv(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    member_service=Depends(get_member_service),
):
    """Importer des membres via un fichier CSV (admin uniquement)."""
    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    require_school_admin(school_id=current_user.school_id, current_user=current_user, db=db)

    file_content = await file.read()
    result = await member_service.importer_csv(
        school_id=current_user.school_id,
        admin_id=current_user.id,
        file_content=file_content,
        filename=file.filename or "import.csv",
    )
    return result


@router.get("/{user_id}")
async def get_member_profile(
    user_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    member_service=Depends(get_member_service),
):
    """Récupère le profil cognitif complet d'un membre (admin uniquement)."""
    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    require_school_admin(school_id=current_user.school_id, current_user=current_user, db=db)

    profile = await member_service.obtenir_profil_membre(
        school_id=current_user.school_id,
        target_user_id=user_id,
        admin_id=current_user.id,
    )
    return profile


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    user_id: str,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
    member_service=Depends(get_member_service),
):
    """Retirer un membre de l'école (admin uniquement)."""
    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    require_school_admin(school_id=current_user.school_id, current_user=current_user, db=db)

    await member_service.supprimer_membre(
        school_id=current_user.school_id,
        target_user_id=user_id,
        admin_id=current_user.id,
    )
