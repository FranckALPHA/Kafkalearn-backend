"""
utils/reward_calculator.py
===========================
Calculates reward plans based on active referral counts.
"""
from app.modules.referral.utils.constants import PLAN_HIERARCHY, REWARD_TIERS, REWARD_DURATION_DAYS


class RewardCalculator:
    """Calculate referral rewards based on number of active referees."""

    PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited"]
    REWARD_TIERS = {
        3: "access",
        6: "premium",
        9: "pro",
        12: "unlimited",
    }
    REWARD_DURATION_DAYS = 30

    def get_next_plan(self, current_plan: str) -> str | None:
        """Get the next plan in the hierarchy.

        Args:
            current_plan: The user's current plan.

        Returns:
            The next plan name, or None if already at the top.
        """
        try:
            current_idx = self.PLAN_HIERARCHY.index(current_plan)
        except ValueError:
            return None
        if current_idx >= len(self.PLAN_HIERARCHY) - 1:
            return None
        return self.PLAN_HIERARCHY[current_idx + 1]

    def calculate_reward_plan(self, nb_filleuls_actifs: int, current_plan: str) -> tuple:
        """Calculate the reward plan based on active referral count.

        Args:
            nb_filleuls_actifs: Number of active referees.
            current_plan: The user's current plan.

        Returns:
            Tuple of (plan_name_or_None, cycle_number).
            cycle is the tier threshold reached (3, 6, 9, 12).
        """
        reward_plan = None
        cycle = 0

        for threshold, plan in sorted(self.REWARD_TIERS.items()):
            if nb_filleuls_actifs >= threshold:
                # Only upgrade if the reward plan is better than current
                try:
                    plan_level = self.PLAN_HIERARCHY.index(plan)
                    current_level = self.PLAN_HIERARCHY.index(current_plan)
                    if plan_level > current_level:
                        reward_plan = plan
                        cycle = threshold
                except ValueError:
                    pass

        return reward_plan, cycle

    def get_reward_value_fcfa(self, plan: str) -> int:
        """Get the approximate monetary value of a reward in FCFA.

        Args:
            plan: The plan name.

        Returns:
            Estimated value in FCFA.
        """
        plan_values = {
            "freemium": 0,
            "access": 2000,
            "premium": 5000,
            "pro": 10000,
            "unlimited": 20000,
        }
        return plan_values.get(plan, 0)
