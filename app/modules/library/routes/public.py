import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.library.schemas.responses import CommunityExploreResponse, AssetDetailResponse
from app.modules.library.routes.dependencies import (
    get_asset_service, get_reco_service, get_current_user, library_explore_rate_limiter, get_rate_limiter_dependency
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library/public", tags=["Library Public"])


@router.get("/", response_model=CommunityExploreResponse)
async def explore_community(
    asset_type: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    class_name: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    tri: str = Query("note_desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    asset_service=Depends(get_asset_service),
    _rate_limit=Depends(get_rate_limiter_dependency(library_explore_rate_limiter)),
):
    """Explore community assets with filters."""
    result = await asset_service.explorer_communaute(
        asset_type=asset_type,
        subject=subject,
        class_name=class_name,
        search=search,
        tri=tri,
        page=page,
        limit=limit,
    )
    return CommunityExploreResponse(
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        assets=result["items"],
    )


@router.get("/recommandes")
async def get_personalized_recommendations(
    current_user: User = Depends(get_current_user),
    reco_service=Depends(get_reco_service),
):
    """Get personalized recommendations for the current user."""
    recommendations = await reco_service.recommander(user_id=current_user.id)
    return {"recommandations": recommendations}


@router.get("/{share_code}", response_model=AssetDetailResponse)
async def get_asset_by_share_code(
    share_code: str,
    current_user: User = Depends(get_current_user),
    asset_service=Depends(get_asset_service),
):
    """Access asset by share code AST-XXXXXX."""
    from app.modules.library.models import PedagogicalAsset

    asset = (
        asset_service.db.query(PedagogicalAsset)
        .filter(PedagogicalAsset.lien_partage == share_code)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")

    try:
        data = await asset_service.recuperer_par_id(asset.id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "PLAN_INSUFFICIENT":
            raise HTTPException(status_code=403, detail="PLAN_INSUFFICIENT")
        raise HTTPException(status_code=400, detail=error_code)

    is_owner = data.get("user_id") == str(current_user.id)
    return AssetDetailResponse(
        id=data["id"],
        titre=data["titre"],
        asset_type=data["asset_type"],
        subject=data.get("subject"),
        class_name=data.get("class_name"),
        serie=data.get("serie"),
        notion=data.get("notion"),
        langue=data["langue"],
        is_public=data["is_public"],
        nb_vues=data["nb_vues"],
        nb_telechargements=data["nb_telechargements"],
        nb_copies=data["nb_copies"],
        note_moyenne=data.get("note_moyenne"),
        nb_notes=data["nb_notes"],
        generation_status=data["generation_status"],
        file_url=data.get("file_url"),
        content_json=data.get("content_json"),
        required_plan=data.get("required_plan"),
        lien_partage=data.get("lien_partage"),
        is_owner=is_owner,
        ma_note=data.get("user_note"),
        created_at=data.get("created_at"),
    )
