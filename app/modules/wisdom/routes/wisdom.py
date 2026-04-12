"""
routes/wisdom.py
================
Endpoints publics pour le module wisdom (daily tip, rating, sharing).
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException

from app.modules.wisdom.schemas.responses import DailyWisdomResponse, ShareResponse
from app.modules.wisdom.routes.dependencies import (
    get_current_user,
    get_wisdom_service,
    wisdom_rate_limiter,
    share_rate_limiter,
    get_rate_limiter_dependency,
)
from app.modules.users.models import User

router = APIRouter(prefix="/wisdom", tags=["wisdom"])


@router.get("/daily", response_model=DailyWisdomResponse)
async def get_daily_wisdom(
    request: Request,
    langue: str = "fr",
    current_user: Optional[User] = Depends(get_current_user),
    wisdom_service=Depends(get_wisdom_service),
    _rate_limit=Depends(get_rate_limiter_dependency(wisdom_rate_limiter)),
):
    """Recupere le conseil de sagesse du jour.

    Si l'utilisateur est authentifie et que c'est la premiere vue,
    marque le tip comme vu.
    """
    target_date = date.today()
    tip_data = await wisdom_service.obtenir_tip_du_jour(
        langue=langue,
        date_cible=target_date,
        user_id=str(current_user.id) if current_user else None,
    )

    is_new = tip_data.get("id") is not None
    is_fallback = tip_data.get("fallback", False)

    return DailyWisdomResponse(
        tip=tip_data.get("content", {}),
        is_new=is_new,
        date=str(target_date),
        language=langue,
        is_fallback=is_fallback,
    )


@router.post("/daily/rate")
async def rate_daily_wisdom(
    request: Request,
    rating: int,
    current_user: User = Depends(get_current_user),
    wisdom_service=Depends(get_wisdom_service),
    _rate_limit=Depends(get_rate_limiter_dependency(wisdom_rate_limiter)),
):
    """Note le conseil du jour (1-5)."""
    if not (1 <= rating <= 5):
        raise HTTPException(status_code=400, detail="RATING_OUT_OF_RANGE")

    target_date = date.today()
    tip_data = await wisdom_service.obtenir_tip_du_jour(
        langue="fr",
        date_cible=target_date,
        user_id=str(current_user.id),
    )

    wisdom_id = tip_data.get("id")
    if wisdom_id is None:
        raise HTTPException(status_code=404, detail="TIP_NOT_FOUND")

    try:
        result = await wisdom_service.noter_tip(
            wisdom_id=wisdom_id,
            user_id=str(current_user.id),
            note=rating,
        )
        return {"nouveau_rating_moyen": result.get("nouveau_rating_moyen")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/daily/share", response_model=ShareResponse)
async def share_daily_wisdom(
    request: Request,
    current_user: User = Depends(get_current_user),
    wisdom_service=Depends(get_wisdom_service),
    _rate_limit=Depends(get_rate_limiter_dependency(share_rate_limiter)),
):
    """Enregistre un partage du conseil du jour et retourne le texte formatte."""
    target_date = date.today()
    tip_data = await wisdom_service.obtenir_tip_du_jour(
        langue="fr",
        date_cible=target_date,
        user_id=str(current_user.id),
    )

    wisdom_id = tip_data.get("id")
    if wisdom_id is None:
        raise HTTPException(status_code=404, detail="TIP_NOT_FOUND")

    share_text = await wisdom_service.enregistrer_partage(
        wisdom_id=wisdom_id,
        user_id=str(current_user.id),
    )

    return ShareResponse(
        message="Partage enregistre avec succes",
        texte_partage=share_text,
    )
