"""
schemas/__init__.py
===================
Export des schémas Pydantic du module users.
"""

from .requests import (
    UserRegisterRequest,
    LoginRequest,
    VerifyRequest,
    PasswordResetRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    OnboardingCompleteRequest,
    RefreshTokenRequest,
    FeedbackRequest,
)
from .responses import (
    AuthResponse,
    UserProfileResponse,
    ProfileStatsResponse,
    MessageResponse,
    PaginatedResponse,
    ReportStatusResponse,
)

__all__ = [
    "UserRegisterRequest",
    "LoginRequest",
    "VerifyRequest",
    "PasswordResetRequest",
    "PasswordChangeRequest",
    "ProfileUpdateRequest",
    "OnboardingCompleteRequest",
    "RefreshTokenRequest",
    "FeedbackRequest",
    "AuthResponse",
    "UserProfileResponse",
    "ProfileStatsResponse",
    "MessageResponse",
    "PaginatedResponse",
    "ReportStatusResponse",
]
