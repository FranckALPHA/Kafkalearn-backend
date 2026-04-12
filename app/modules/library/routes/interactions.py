import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.modules.library.schemas.requests import AssetRatingRequest
from app.modules.library.routes.dependencies import (
    get_asset_service, get_rating_service, get_current_user,
    library_copy_rate_limiter, library_rate_rate_limiter, get_rate_limiter_dependency
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library/interactions", tags=["Library Interactions"])


@router.post("/{asset_id}/copy", status_code=201)
async def copy_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    asset_service=Depends(get_asset_service),
    _rate_limit=Depends(get_rate_limiter_dependency(library_copy_rate_limiter)),
):
    """Copy a public asset to user's library."""
    try:
        result = await asset_service.copier_asset_public(asset_id, current_user.id)
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")
        if error_code == "NOT_PUBLIC":
            raise HTTPException(status_code=403, detail="ASSET_NOT_PUBLIC")
        if error_code == "OWN_ASSET":
            raise HTTPException(status_code=400, detail="OWN_ASSET")
        if error_code == "ALREADY_COPIED":
            raise HTTPException(status_code=409, detail="ALREADY_COPIED")
        raise HTTPException(status_code=400, detail=error_code)

    return result


@router.post("/{asset_id}/rate")
async def rate_asset(
    asset_id: int,
    payload: AssetRatingRequest,
    current_user: User = Depends(get_current_user),
    rating_service=Depends(get_rating_service),
    _rate_limit=Depends(get_rate_limiter_dependency(library_rate_rate_limiter)),
):
    """Rate a public asset."""
    try:
        result = await rating_service.noter_asset(
            asset_id=asset_id,
            user_id=current_user.id,
            note=payload.note,
            commentaire=payload.commentaire,
        )
    except ValueError as e:
        error_code = str(e)
        if error_code == "NOT_FOUND":
            raise HTTPException(status_code=404, detail="ASSET_NOT_FOUND")
        if error_code == "NOT_PUBLIC":
            raise HTTPException(status_code=403, detail="ASSET_NOT_PUBLIC")
        if error_code == "CANNOT_RATE_OWN":
            raise HTTPException(status_code=400, detail="CANNOT_RATE_OWN")
        if error_code == "INVALID_NOTE":
            raise HTTPException(status_code=400, detail="INVALID_NOTE")
        raise HTTPException(status_code=400, detail=error_code)

    return result
