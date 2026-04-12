"""
utils/constants.py
==================
Constants for the referral system: plan hierarchy, reward tiers, durations.
"""

PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited", "school"]

REWARD_TIERS = {
    3: "access",
    6: "premium",
    9: "pro",
    12: "unlimited",
}

REWARD_DURATION_DAYS = 30

REFERRAL_CODE_LENGTH = 6

REFERRAL_BONUS_DURATION = 30
