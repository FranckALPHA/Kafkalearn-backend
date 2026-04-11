"""
schemas/requests.py
===================
Schémas Pydantic pour les requêtes du module skills.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class SkillRunRequest(BaseModel):
    """Requête pour exécuter un skill."""

    prompt: str = Field(..., min_length=3, max_length=2000, description="Prompt utilisateur")
    skill: Optional[str] = Field(None, description="Skill explicite (fiche, quiz, solver, etc.)")
    chat_session_id: Optional[str] = Field(None, description="ID de session de chat existante")
    langue: Optional[str] = Field("fr", description="Langue de réponse")
    params: Dict[str, Any] = Field(default_factory=dict, description="Paramètres du skill")
    avec_rag: bool = Field(True, description="Utiliser le contexte RAG")
    user_document_id: Optional[int] = Field(None, description="Document personnel à utiliser")
    idempotency_key: Optional[str] = Field(None, max_length=100)

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le prompt ne peut pas être vide")
        return v.strip()


class QuizSubmitRequest(BaseModel):
    """Soumission des réponses à un quiz."""

    reponses: Dict[int, str] = Field(..., description="{question_id: réponse}")
    duree_secondes: Optional[int] = Field(None, ge=0, description="Temps mis pour répondre")


class DetectIntentRequest(BaseModel):
    """Détection d'intention sans exécution."""

    texte: str = Field(..., min_length=2, max_length=500)

    @field_validator("texte")
    @classmethod
    def texte_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le texte ne peut pas être vide")
        return v.strip()


class ChatMessageRequest(BaseModel):
    """Envoi d'un message dans une session de chat."""

    content: str = Field(..., min_length=1, max_length=5000)
    skill: Optional[str] = Field(None, description="Skill à utiliser")
    params: Dict[str, Any] = Field(default_factory=dict)
