"""
routes/admin.py
===============
Endpoints d'analytics SuperAdmin pour le module search.
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.modules.search.routes.dependencies import (
    get_db,
    get_current_user,
    get_analytics_service,
)
from app.modules.search.schemas.responses import SearchAnalyticsResponse
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/search", tags=["Admin - Search Analytics"])


@router.get("/analytics", response_model=SearchAnalyticsResponse)
async def get_search_analytics(
    period: str = Query("7d", description="Période: 7d, 30d, 90d"),
    current_user: User = Depends(get_current_user),
    analytics_service=Depends(get_analytics_service),
):
    """
    Statistiques de recherche pour SuperAdmin.
    """
    if current_user.role not in ("superadmin", "admin"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")

    data = analytics_service.get_analytics(period=period)
    return SearchAnalyticsResponse(**data)


@router.get("/popular-queries")
async def get_popular_queries(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    analytics_service=Depends(get_analytics_service),
):
    """Requêtes les plus fréquentes."""
    if current_user.role not in ("superadmin", "admin"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")

    return {"queries": analytics_service.get_popular_queries(limit=limit)}
