"""
routes/referral.py
==================
Public referral endpoints for users.
"""
import logging
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.modules.referral.schemas.responses import (
    ReferralStatsResponse,
    RewardTiersResponse,
)
from app.modules.referral.routes.dependencies import (
    get_db,
    get_current_user,
    get_referral_service,
    get_qr_service,
    get_rate_limiter_dependency,
    referral_rate_limiter,
    qr_code_rate_limiter,
)
from app.modules.referral.utils.constants import REWARD_TIERS, REWARD_DURATION_DAYS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/referral", tags=["Referral"])


@router.get(
    "/me",
    response_model=ReferralStatsResponse,
)
async def get_my_referral_stats(
    current_user=Depends(get_current_user),
    referral_service=Depends(get_referral_service),
):
    """Get the current user's referral statistics and info."""
    stats = referral_service.obtenir_stats_parrain(str(current_user.id))
    return ReferralStatsResponse(**stats)


@router.get(
    "/check/{code}",
    dependencies=[Depends(get_rate_limiter_dependency(referral_rate_limiter))],
)
async def check_referral_code(
    code: str,
    referral_service=Depends(get_referral_service),
):
    """Validate a referral code (public, rate limited 20/min)."""
    result = referral_service.verifier_code_parrainage(code)
    return result


@router.get(
    "/rewards",
    response_model=RewardTiersResponse,
)
async def get_reward_tiers():
    """Get referral reward tiers information (public)."""
    paliers = []
    for threshold, plan in sorted(REWARD_TIERS.items()):
        paliers.append({
            "nb_filleuls": threshold,
            "plan_recompense": plan,
            "duree_jours": REWARD_DURATION_DAYS,
        })

    return RewardTiersResponse(
        description="Parrainez des amis et gagnez des upgrades gratuits!",
        mecanisme="Pour chaque ami qui rejoint KafkaLearn via votre code et devient actif (premiere recherche ou premier paiement), vous gagnez un point. A chaque palier atteint, votre plan est upgrade pour une duree de 30 jours.",
        paliers=paliers,
        definition_actif="Un filleul est considere actif lorsqu'il effectue sa premiere recherche ou son premier paiement sur la plateforme.",
    )


@router.get(
    "/me/qr-code",
    dependencies=[Depends(get_rate_limiter_dependency(qr_code_rate_limiter))],
)
async def get_my_qr_code(
    current_user=Depends(get_current_user),
    referral_service=Depends(get_referral_service),
    qr_service=Depends(get_qr_service),
):
    """Get a QR code for the user's referral link (rate limited 10/hour)."""
    stats = referral_service.obtenir_stats_parrain(str(current_user.id))
    referral_link = stats["referral_link"]

    qr_bytes = await qr_service.generer_avec_cache(str(current_user.id), referral_link)

    if not qr_bytes:
        return Response(
            content="QR code generation failed - qrcode[pil] not installed",
            status_code=500,
            media_type="text/plain",
        )

    return Response(
        content=qr_bytes,
        media_type="image/png",
    )
