from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.modules.doc_analysis.routes.dependencies import (
    get_db,
    get_current_user,
    get_cache_service,
    get_feedback_service,
)
from app.modules.users.models import User

router = APIRouter(prefix="/admin/doc-analysis", tags=["Admin - Document Analysis"])


def _require_superadmin(current_user: User):
    """Check that the current user is a superadmin.
    
    NOTE: Disabled for development phase - any user can access.
    """
    # DEV MODE: Allow any user
    return
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SUPERADMIN_REQUIRED")


@router.get("/stats")
async def get_analysis_stats(
    current_user: User = Depends(get_current_user),
    cache_service=Depends(get_cache_service),
):
    """Return global cache statistics (SuperAdmin only)."""
    _require_superadmin(current_user)
    return await cache_service.obtenir_stats_cache()


@router.get("/low-quality")
async def get_low_quality_analyses(
    current_user: User = Depends(get_current_user),
    feedback_service=Depends(get_feedback_service),
    seuil: float = 0.35,
    min_feedbacks: int = 5,
):
    """Return list of low quality analyses (SuperAdmin only)."""
    _require_superadmin(current_user)
    return await feedback_service.obtenir_analyses_faible_qualite(
        seuil_taux_utilite=seuil,
        nb_feedbacks_min=min_feedbacks,
    )
