"""
routes/admin.py
===============
Endpoints d'analytics SuperAdmin pour le module skills.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.skills.routes.dependencies import (
    get_db,
    get_current_user,
    get_analytics_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/skills", tags=["Admin - Skills Analytics"])


@router.get("/analytics")
async def get_skills_analytics(
    period: str = Query("7d", description="Période: 7d, 30d, 90d"),
    current_user: User = Depends(get_current_user),
    analytics_service=Depends(get_analytics_service),
):
    """Statistiques d'utilisation des skills pour SuperAdmin."""
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")

    return analytics_service.get_analytics(period=period)


@router.get("/top-skills")
async def get_top_skills(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    analytics_service=Depends(get_analytics_service),
):
    """Skills les plus utilisés."""
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")

    return {"skills": analytics_service.get_top_skills(limit=limit)}


@router.get("/top-matieres")
async def get_top_matieres(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    analytics_service=Depends(get_analytics_service),
):
    """Matières les plus pratiquées."""
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")

    return {"matieres": analytics_service.get_top_matieres(limit=limit)}
