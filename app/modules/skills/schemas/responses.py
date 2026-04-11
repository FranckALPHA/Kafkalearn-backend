"""
schemas/responses.py
====================
Schémas Pydantic pour les réponses du module skills.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class SkillResultResponse(BaseModel):
    """Réponse d'exécution de skill."""

    success: bool
    skill_type: str
    output_type: str
    content: Optional[str] = None
    file_url: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    latence_ms: Optional[int] = None
    erreur_code: Optional[str] = None

    @classmethod
    def from_skill_result(cls, result, session_id: str = None):
        return cls(
            success=result.success,
            skill_type=result.skill_type,
            output_type=result.output_type,
            content=result.data.get("titre") if result.data else None,
            file_url=result.file_url,
            json_data=result.json_data,
            metadata=result.data,
            session_id=session_id,
            latence_ms=result.latence_ms,
            erreur_code=result.erreur_code,
        )


class QuizCorrectionResponse(BaseModel):
    """Réponse de correction de quiz."""

    quiz_session_id: str
    score_percent: float
    nb_bonnes_reponses: int
    nb_mauvaises_reponses: int
    is_passing: bool
    corrections: List[Dict[str, Any]]
    duree_secondes: Optional[int] = None
    lacunes_detectees: Optional[List[Dict[str, Any]]] = None
    lacune_detectee: Optional[str] = None
    matiere: Optional[str] = None


class SkillListResponse(BaseModel):
    """Catalogue des skills disponibles."""

    skills: List[Dict[str, Any]]


class IntentDetectionResponse(BaseModel):
    """Réponse de détection d'intention."""

    skill_detecte: Optional[str] = None
    confidence: str  # high, medium, low
    methode: str  # regex, llm, fallback
    params_extraits: Dict[str, Any] = {}
    alternatives: List[str] = []


class ChatSessionResponse(BaseModel):
    """Réponse pour une session de chat."""

    id: str
    titre: str
    skill_predominant: Optional[str] = None
    matiere: Optional[str] = None
    nb_messages: int = 0
    note_utilisateur: Optional[int] = None
    is_pinned: bool = False
    last_message_preview: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Réponse pour un message de chat."""

    id: int
    role: str
    content: str
    skill_utilise: Optional[str] = None
    output_type: Optional[str] = None
    file_url: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None
    feedback: Optional[int] = None
    created_at: Optional[str] = None


class ChatSessionListResponse(BaseModel):
    """Liste des sessions de chat."""

    sessions: List[ChatSessionResponse]
    total: int


class ChatMessageListResponse(BaseModel):
    """Liste des messages d'une session."""

    messages: List[ChatMessageResponse]
    total: int
