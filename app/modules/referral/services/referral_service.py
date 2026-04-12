"""
services/referral_service.py
=============================
Core referral business logic: registration, activation, rewards, stats.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.referral.models import ReferralActivity, ReferralReward
from app.modules.referral.utils.referral_code_generator import ReferralCodeGenerator
from app.modules.referral.utils.reward_calculator import RewardCalculator
from app.modules.referral.utils.constants import REWARD_TIERS, REWARD_DURATION_DAYS, PLAN_HIERARCHY
from app.modules.referral.services.base import ReferralBaseService
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class ReferralService(ReferralBaseService):
    """Manages the complete referral lifecycle."""

    def enregistrer_parrainage(
        self,
        referrer_id: str,
        referee_id: str,
        canal: str = "lien_direct",
    ) -> bool:
        """Register a new referral relationship.

        Args:
            referrer_id: UUID of the referrer.
            referee_id: UUID of the new user being referred.
            canal: Acquisition channel (lien_direct, qr_code, partage_whatsapp, sms, autre).

        Returns:
            True if the referral was registered successfully.

        Raises:
            ValueError: If self-referral or already referred.
        """
        # Check self-referral
        if referrer_id == referee_id:
            raise ValueError("AUTO_PARRAINAGE_INTERDIT")

        # Check if already referred
        existing = (
            self.db.query(ReferralActivity)
            .filter(ReferralActivity.referee_id == referee_id)
            .first()
        )
        if existing:
            raise ValueError("DEJA_PARRAINE")

        # Create the referral activity
        activity = ReferralActivity(
            referrer_id=referrer_id,
            referee_id=referee_id,
            is_active=False,
            canal_acquisition=canal,
        )
        self.db.add(activity)
        self.db.commit()

        # Update the referee's referred_by
        referee = self.db.query(User).filter(User.id == referee_id).first()
        if referee:
            referee.referred_by_id = referrer_id
            self.db.commit()

        return True

    def verifier_code_parrainage(self, code: str) -> dict:
        """Validate a referral code and return referrer info.

        Args:
            code: The 6-character referral code to validate.

        Returns:
            Dict with valide, parrain_prenom, avantage.
        """
        if not ReferralCodeGenerator.validate(code):
            return {"valide": False, "parrain_prenom": None, "avantage": "Code invalide"}

        referrer = (
            self.db.query(User)
            .filter(User.referral_code == code, User.is_deleted == False)
            .first()
        )
        if not referrer:
            return {"valide": False, "parrain_prenom": None, "avantage": "Code introuvable"}

        # Count active referrals to show advantage
        nb_actifs = (
            self.db.query(ReferralActivity)
            .filter(
                ReferralActivity.referrer_id == referrer.id,
                ReferralActivity.is_active == True,
            )
            .count()
        )

        # Calculate next reward
        calculator = RewardCalculator()
        next_threshold = None
        for threshold in sorted(REWARD_TIERS.keys()):
            if nb_actifs < threshold:
                next_threshold = threshold
                break

        avantage = ""
        if next_threshold:
            plan = REWARD_TIERS.get(next_threshold, "")
            restants = next_threshold - nb_actifs
            avantage = f"Plus que {restants} filleul(s) actif(s) pour le plan {plan}"
        else:
            avantage = "Tous les paliers atteints"

        return {
            "valide": True,
            "parrain_prenom": referrer.prenom,
            "avantage": avantage,
        }

    def marquer_filleul_actif(self, referee_id: str) -> dict:
        """Mark a referred user as active (first search or payment).

        Args:
            referee_id: UUID of the referred user.

        Returns:
            Dict with activated, reward_applied, reward_plan, reason.
        """
        activity = (
            self.db.query(ReferralActivity)
            .filter(ReferralActivity.referee_id == referee_id)
            .first()
        )

        if not activity:
            return {
                "activated": False,
                "reward_applied": False,
                "reward_plan": None,
                "reason": "Aucun parrainage trouve",
            }

        if activity.is_active:
            return {
                "activated": False,
                "reward_applied": False,
                "reward_plan": None,
                "reason": "Deja actif",
            }

        # Mark as active
        activity.is_active = True
        activity.date_activation = func.now()
        self.db.commit()

        # Get referrer info for notification
        referrer_id = activity.referrer_id
        referee = self.db.query(User).filter(User.id == referee_id).first()
        referee_prenom = referee.prenom if referee else ""

        # Check and apply reward
        reward_result = self.verifier_et_appliquer_recompense(referrer_id)

        # Send notification to referrer
        self._notifier_parrain_activation(referrer_id, referee_prenom)

        return {
            "activated": True,
            "reward_applied": reward_result["applied"],
            "reward_plan": reward_result["plan"],
            "reason": None,
        }

    def verifier_et_appliquer_recompense(self, referrer_id: str) -> dict:
        """Check if the referrer qualifies for a reward and apply it.

        Args:
            referrer_id: UUID of the referrer.

        Returns:
            Dict with applied, plan, cycle.
        """
        nb_actifs = self.compter_filleuls_actifs(referrer_id)
        referrer = self.db.query(User).filter(User.id == referrer_id).first()
        if not referrer:
            return {"applied": False, "plan": None, "cycle": 0}

        current_plan = referrer.plan_effectif
        calculator = RewardCalculator()
        reward_plan, cycle = calculator.calculate_reward_plan(nb_actifs, current_plan)

        if not reward_plan:
            return {"applied": False, "plan": None, "cycle": 0}

        # Check if this cycle was already rewarded
        existing_reward = (
            self.db.query(ReferralReward)
            .filter(
                ReferralReward.user_id == referrer_id,
                ReferralReward.nb_filleuls_atteint == cycle,
            )
            .first()
        )
        if existing_reward:
            # Check if still active (not expired)
            if existing_reward.is_active:
                return {"applied": False, "plan": None, "cycle": 0}

        # Apply the reward: upgrade plan
        plan_avant = referrer.plan_effectif
        referrer.plan_effectif = reward_plan
        expiration_at = datetime.utcnow() + timedelta(days=REWARD_DURATION_DAYS)
        referrer.plan_expiration_at = expiration_at

        # Create reward record
        reward = ReferralReward(
            user_id=referrer_id,
            nb_filleuls_atteint=cycle,
            plan_avant=plan_avant,
            plan_apres=reward_plan,
            duree_jours=REWARD_DURATION_DAYS,
            expiration_at=expiration_at,
        )
        self.db.add(reward)

        # Mark activities as reward applied
        (
            self.db.query(ReferralActivity)
            .filter(
                ReferralActivity.referrer_id == referrer_id,
                ReferralActivity.recompense_appliquee == False,
            )
            .update(
                {
                    "recompense_appliquee": True,
                    "recompense_applied_at": func.now(),
                }
            )
        )

        self.db.commit()

        # Send notification
        self._notifier_parrain_recompense(referrer_id, reward_plan, cycle)

        return {"applied": True, "plan": reward_plan, "cycle": cycle}

    def _notifier_parrain_activation(self, referrer_id: str, referee_prenom: str) -> None:
        """Enqueue notification task for referrer about referee activation."""
        try:
            from app.modules.referral.jobs.tasks import notify_referral_active_task
            notify_referral_active_task.delay(str(referrer_id), referee_prenom)
        except Exception as e:
            logger.warning("Failed to enqueue referral activation notification: %s", e)

    def _notifier_parrain_recompense(self, referrer_id: str, plan: str, cycle: int) -> None:
        """Enqueue notification task for referrer about reward received."""
        try:
            from app.modules.referral.jobs.tasks import notify_referral_reward_task
            notify_referral_reward_task.delay(str(referrer_id), plan, cycle)
        except Exception as e:
            logger.warning("Failed to enqueue referral reward notification: %s", e)

    def compter_filleuls_actifs(self, referrer_id: str) -> int:
        """Count the number of active referees for a referrer.

        Args:
            referrer_id: UUID of the referrer.

        Returns:
            Number of active referees.
        """
        return (
            self.db.query(ReferralActivity)
            .filter(
                ReferralActivity.referrer_id == referrer_id,
                ReferralActivity.is_active == True,
            )
            .count()
        )

    def lister_mes_filleuls(self, referrer_id: str, mask_email: bool = True) -> list:
        """List all referees for a referrer.

        Args:
            referrer_id: UUID of the referrer.
            mask_email: Whether to mask referee emails.

        Returns:
            List of serialized referral activity dicts.
        """
        activities = (
            self.db.query(ReferralActivity)
            .filter(ReferralActivity.referrer_id == referrer_id)
            .order_by(ReferralActivity.date_ref.desc())
            .all()
        )
        return [act.serialize_for_list(mask_email=mask_email) for act in activities]

    def obtenir_stats_parrain(self, referrer_id: str) -> dict:
        """Get comprehensive referral stats for a referrer.

        Args:
            referrer_id: UUID of the referrer.

        Returns:
            Dict with all referral stats.
        """
        referrer = self.db.query(User).filter(User.id == referrer_id).first()
        if not referrer:
            raise ValueError("USER_NOT_FOUND")

        referral_code = referrer.referral_code or ""
        frontend_url = "https://kafkalearn.app"
        referral_link = f"{frontend_url}/register?ref={referral_code}"

        nb_total = (
            self.db.query(ReferralActivity)
            .filter(ReferralActivity.referrer_id == referrer_id)
            .count()
        )
        nb_actifs = self.compter_filleuls_actifs(referrer_id)

        # Current cycle info
        calculator = RewardCalculator()
        cycle_actuel = 0
        filleuls_restants = 0
        prochain_bonus = None

        for threshold in sorted(REWARD_TIERS.keys()):
            if nb_actifs >= threshold:
                cycle_actuel = threshold
            else:
                filleuls_restants = threshold - nb_actifs
                prochain_bonus = {
                    "nb_filleuls_requis": threshold,
                    "plan_recompense": REWARD_TIERS[threshold],
                    "filleuls_manquants": filleuls_restants,
                }
                break

        # Active rewards
        active_rewards = (
            self.db.query(ReferralReward)
            .filter(
                ReferralReward.user_id == referrer_id,
                ReferralReward.expiration_at > func.now(),
            )
            .all()
        )

        # Check if user has a referrer
        has_referrer = referrer.referred_by_id is not None
        referrer_prenom = None
        if has_referrer:
            parrain = (
                self.db.query(User)
                .filter(User.id == referrer.referred_by_id)
                .first()
            )
            if parrain:
                referrer_prenom = parrain.prenom

        liste_filleuls = self.lister_mes_filleuls(referrer_id)

        return {
            "referral_code": referral_code,
            "referral_link": referral_link,
            "nb_filleuls_total": nb_total,
            "nb_filleuls_actifs": nb_actifs,
            "has_referrer": has_referrer,
            "referrer_prenom": referrer_prenom,
            "cycle_actuel": cycle_actuel,
            "filleuls_dans_cycle_actuel": nb_actifs - cycle_actuel if nb_actifs > cycle_actuel else 0,
            "filleuls_restants_pour_bonus": filleuls_restants,
            "prochain_bonus": prochain_bonus,
            "recompenses_actives": [r.serialize() for r in active_rewards],
            "liste_filleuls": liste_filleuls,
        }
