"""
services/referral_analytics.py
===============================
Analytics and reporting for the referral system.
"""
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.referral.models import ReferralActivity, ReferralReward
from app.modules.referral.services.base import ReferralBaseService
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class ReferralAnalytics(ReferralBaseService):
    """Generate analytics and reports for the referral program."""

    def get_stats_globales(self) -> dict:
        """Get global referral program statistics.

        Returns:
            Dict with total_referrals, active_referrals, conversion_rate,
            rewards_given, top_referrers.
        """
        total_referrals = self.db.query(ReferralActivity).count()
        active_referrals = (
            self.db.query(ReferralActivity)
            .filter(ReferralActivity.is_active == True)
            .count()
        )

        conversion_rate = 0.0
        if total_referrals > 0:
            conversion_rate = round((active_referrals / total_referrals) * 100, 2)

        rewards_given = (
            self.db.query(ReferralReward)
            .filter(ReferralReward.expiration_at > func.now())
            .count()
        )

        # Top referrers (top 5 by active referrals)
        top_referrers_raw = (
            self.db.query(
                ReferralActivity.referrer_id,
                func.count(ReferralActivity.id).label("nb_actifs"),
            )
            .filter(ReferralActivity.is_active == True)
            .group_by(ReferralActivity.referrer_id)
            .order_by(func.count(ReferralActivity.id).desc())
            .limit(5)
            .all()
        )

        top_referrers = []
        for ref_id, nb in top_referrers_raw:
            user = self.db.query(User).filter(User.id == ref_id).first()
            if user:
                prenom = user.prenom or ""
                masked = prenom[:2] + "***" if len(prenom) > 2 else "***"
                top_referrers.append({
                    "referrer_id": str(ref_id),
                    "prenom": masked,
                    "nb_filleuls_actifs": nb,
                })

        return {
            "total_referrals": total_referrals,
            "active_referrals": active_referrals,
            "conversion_rate": conversion_rate,
            "rewards_given": rewards_given,
            "top_referrers": top_referrers,
        }

    def get_top_parrains(self, limit: int = 10) -> list:
        """Get top referrers by active referral count.

        Args:
            limit: Maximum number of referrers to return.

        Returns:
            List of dicts with prenom (masked), nb_filleuls_actifs, nb_recompenses.
        """
        top_referrers_raw = (
            self.db.query(
                ReferralActivity.referrer_id,
                func.count(ReferralActivity.id).label("nb_actifs"),
            )
            .filter(ReferralActivity.is_active == True)
            .group_by(ReferralActivity.referrer_id)
            .order_by(func.count(ReferralActivity.id).desc())
            .limit(limit)
            .all()
        )

        result = []
        for ref_id, nb_actifs in top_referrers_raw:
            user = self.db.query(User).filter(User.id == ref_id).first()
            if not user:
                continue

            prenom = user.prenom or ""
            masked = prenom[:2] + "***" if len(prenom) > 2 else "***"

            nb_recompenses = (
                self.db.query(ReferralReward)
                .filter(ReferralReward.user_id == ref_id)
                .count()
            )

            result.append({
                "referrer_id": str(ref_id),
                "prenom": masked,
                "nb_filleuls_actifs": nb_actifs,
                "nb_recompenses": nb_recompenses,
            })

        return result

    def get_leaderboard(self, limit: int = 10) -> list:
        """Get referral leaderboard with full details.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of dicts with rang, prenom, nb_filleuls_actifs, plan_actuel,
            nb_recompenses_recues.
        """
        top_referrers_raw = (
            self.db.query(
                ReferralActivity.referrer_id,
                func.count(ReferralActivity.id).label("nb_actifs"),
            )
            .filter(ReferralActivity.is_active == True)
            .group_by(ReferralActivity.referrer_id)
            .order_by(func.count(ReferralActivity.id).desc())
            .limit(limit)
            .all()
        )

        leaderboard = []
        for rang, (ref_id, nb_actifs) in enumerate(top_referrers_raw, start=1):
            user = self.db.query(User).filter(User.id == ref_id).first()
            if not user:
                continue

            prenom = user.prenom or ""
            masked = prenom[:2] + "***" if len(prenom) > 2 else "***"

            nb_recompenses = (
                self.db.query(ReferralReward)
                .filter(ReferralReward.user_id == ref_id)
                .count()
            )

            leaderboard.append({
                "rang": rang,
                "prenom": masked,
                "nb_filleuls_actifs": nb_actifs,
                "plan_actuel": user.plan_effectif,
                "nb_recompenses_recues": nb_recompenses,
            })

        return leaderboard
