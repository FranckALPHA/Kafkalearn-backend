"""
routes/admin.py
===============
Admin-only referral endpoints for monitoring and management.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.modules.referral.schemas.responses import LeaderboardResponse
from app.modules.referral.routes.dependencies import (
    get_db,
    get_current_user,
    get_analytics_service,
    get_referral_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/referral", tags=["Admin - Referral"])


async def _require_admin(current_user=Depends(get_current_user)):
    """Verify the current user is an admin or superadmin."""
    if current_user.role not in ("admin", "superadmin"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")
    return current_user


@router.get("/stats")
async def get_global_stats(
    admin=Depends(_require_admin),
    analytics_service=Depends(get_analytics_service),
):
    """Get global referral program statistics (admin only)."""
    return analytics_service.get_stats_globales()


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
)
async def get_leaderboard(
    admin=Depends(_require_admin),
    analytics_service=Depends(get_analytics_service),
):
    """Get the referral leaderboard (admin only)."""
    leaderboard = analytics_service.get_leaderboard(limit=10)
    return LeaderboardResponse(leaderboard=leaderboard)


@router.post("/verify-rewards")
async def verify_and_apply_rewards(
    admin=Depends(_require_admin),
    referral_service=Depends(get_referral_service),
):
    """Check and apply pending rewards for all active referrers (admin only).

    This endpoint iterates through users with active referrals and checks
    if any qualify for rewards that haven't been applied yet.
    """
    from app.modules.referral.models import ReferralActivity
    from sqlalchemy import func

    db = referral_service.db

    # Find all referrers with at least 3 active referrals
    referrers_with_actives = (
        db.query(
            ReferralActivity.referrer_id,
            func.count(ReferralActivity.id).label("nb_actifs"),
        )
        .filter(ReferralActivity.is_active == True)
        .group_by(ReferralActivity.referrer_id)
        .having(func.count(ReferralActivity.id) >= 3)
        .all()
    )

    applied_count = 0
    results = []

    for referrer_id, nb_actifs in referrers_with_actives:
        try:
            result = referral_service.verifier_et_appliquer_recompense(str(referrer_id))
            if result["applied"]:
                applied_count += 1
                results.append({
                    "referrer_id": str(referrer_id),
                    "applied": True,
                    "plan": result["plan"],
                    "cycle": result["cycle"],
                })
        except Exception as e:
            logger.warning(
                "Failed to check rewards for referrer %s: %s", referrer_id, e
            )
            results.append({
                "referrer_id": str(referrer_id),
                "applied": False,
                "error": str(e),
            })

    return {
        "total_checked": len(referrers_with_actives),
        "rewards_applied": applied_count,
        "details": results,
    }
