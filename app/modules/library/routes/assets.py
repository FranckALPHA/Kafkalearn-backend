import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.library.schemas.requests import AssetShareRequest, AssetUpdateRequest
from app.modules.library.schemas.responses import AssetListResponse, AssetDetailResponse, ShareCodeResponse
from app.modules.library.routes.dependencies import get_asset_service, get_current_user
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library", tags=["Library Assets"])


@router.get("/", response_model=AssetListResponse)
async def list_personal_assets(
    asset_type: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    tri: str = Query("date_desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    asset_service=Depends(get_asset_service),
):
    """List personal assets with filters."""
    result = await asset_service.lister_assets_utilisateur(
        user_id=current_user.id,
        asset_type=asset_type,
        subject=subject,
        search=search,
        tri=tri,
        page=page,
        limit=limit,
    )
    return AssetListResponse(
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        assets=result["items"],
    )


@router.get("/{asset_id}", response_model=AssetDetailResponse)
async def get_asset_detail(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    asset_service=Depends(get_asset_service),
):
    """Get asset detail with access checks."""
    try:
        data = await asset_service.recuperer_par_id(asset_id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")
        if error_code == "NOT_OWNER":
            raise HTTPException(status_code=403, detail="NOT_OWNER")
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


@router.patch("/{asset_id}")
async def update_asset(
    asset_id: int,
    payload: AssetUpdateRequest,
    current_user: User = Depends(get_current_user),
    asset_service=Depends(get_asset_service),
):
    """Update asset metadata fields."""
    try:
        asset = asset_service._verify_ownership(asset_id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")
        if error_code == "NOT_OWNER":
            raise HTTPException(status_code=403, detail="NOT_OWNER")
        raise HTTPException(status_code=400, detail=error_code)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asset, field, value)

    asset_service.db.commit()
    asset_service.db.refresh(asset)
    return {"message": "Asset updated", "asset": asset.serialize_list_item(is_owner=True)}


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    asset_service=Depends(get_asset_service),
):
    """Delete asset."""
    try:
        await asset_service.supprimer_asset(asset_id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")
        if error_code == "NOT_OWNER":
            raise HTTPException(status_code=403, detail="NOT_OWNER")
        raise HTTPException(status_code=400, detail=error_code)


@router.post("/{asset_id}/share", response_model=ShareCodeResponse)
async def share_asset(
    asset_id: int,
    payload: AssetShareRequest,
    current_user: User = Depends(get_current_user),
    asset_service=Depends(get_asset_service),
):
    """Share/unshare an asset."""
    try:
        result = await asset_service.partager_asset(asset_id, current_user.id, payload.is_public)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")
        if error_code == "NOT_OWNER":
            raise HTTPException(status_code=403, detail="NOT_OWNER")
        raise HTTPException(status_code=400, detail=error_code)

    return ShareCodeResponse(**result)
