"""
routes/admin.py
===============
Endpoints admin pour le module wisdom (stats, top tips).
Reserve aux superadmins.
"""
from fastapi import APIRouter, Depends

from app.modules.wisdom.routes.dependencies import (
    get_current_superadmin,
    get_wisdom_analytics_service,
)
from app.modules.users.models import User

router = APIRouter(prefix="/admin/wisdom", tags=["admin-wisdom"])


@router.get("/stats")
async def get_wisdom_stats(
    current_user: User = Depends(get_current_superadmin),
    analytics_service=Depends(get_wisdom_analytics_service),
):
    """Statistiques globales sur les wisdom tips (SuperAdmin uniquement)."""
    stats = await analytics_service.obtenir_stats_globales()
    return stats


@router.get("/top")
async def get_top_wisdom_tips(
    limit: int = 10,
    current_user: User = Depends(get_current_superadmin),
    analytics_service=Depends(get_wisdom_analytics_service),
):
    """Top des conseils les mieux notes (SuperAdmin uniquement)."""
    top_tips = await analytics_service.obtenir_top_citations(limit=limit)
    return {"top_tips": top_tips}
