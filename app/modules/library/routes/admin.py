import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.library.schemas.responses import LibraryStatsResponse
from app.modules.library.routes.dependencies import get_stats_service, get_current_user
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/library", tags=["Admin Library"])


def _require_superadmin(user: User):
    """Check if user is superadmin or admin."""
    if user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="SUPERADMIN_REQUIRED")


@router.get("/stats", response_model=LibraryStatsResponse)
async def get_library_stats(
    current_user: User = Depends(get_current_user),
    stats_service=Depends(get_stats_service),
):
    """Get global library stats (SuperAdmin only)."""
    _require_superadmin(current_user)

    stats = stats_service.get_stats_globales()
    top_assets = stats_service.get_top_assets(limit=10)

    return LibraryStatsResponse(
        total_assets=stats["total_assets"],
        assets_publics=stats["public_assets"],
        assets_par_type=stats["by_type"],
        assets_gener_7j=stats["generated_7j"],
        taux_partage=stats["share_rate"],
        top_assets=top_assets,
    )


@router.get("/top")
async def get_top_assets(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    stats_service=Depends(get_stats_service),
):
    """Get top assets (SuperAdmin only)."""
    _require_superadmin(current_user)
    return stats_service.get_top_assets(limit=limit)
