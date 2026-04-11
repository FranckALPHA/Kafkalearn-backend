"""
schemas/__init__.py
===================
Export des schémas du module skills.
"""
from .requests import (
    SkillRunRequest,
    QuizSubmitRequest,
    DetectIntentRequest,
    ChatMessageRequest,
)
from .responses import (
    SkillResultResponse,
    QuizCorrectionResponse,
    SkillListResponse,
    IntentDetectionResponse,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatSessionListResponse,
    ChatMessageListResponse,
)

__all__ = [
    "SkillRunRequest",
    "QuizSubmitRequest",
    "DetectIntentRequest",
    "ChatMessageRequest",
    "SkillResultResponse",
    "QuizCorrectionResponse",
    "SkillListResponse",
    "IntentDetectionResponse",
    "ChatSessionResponse",
    "ChatMessageResponse",
    "ChatSessionListResponse",
    "ChatMessageListResponse",
]
