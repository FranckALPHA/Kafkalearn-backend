"""
services/__init__.py
====================
Export des services du module users.
"""
from .base import BaseService
from .user_service import UserService
from .learning_profile_service import LearningProfileService
from .streak_service import StreakService
from .score_global_service import ScoreGlobalService
from .churn_detector_service import ChurnDetectorService
from .onboarding_service import OnboardingService
from .profile_report_service import ProfileReportService
from .audit_service import AuditService
from .mail_service import MailService

__all__ = [
    "BaseService",
    "UserService",
    "LearningProfileService",
    "StreakService",
    "ScoreGlobalService",
    "ChurnDetectorService",
    "OnboardingService",
    "ProfileReportService",
    "AuditService",
    "MailService",
]
