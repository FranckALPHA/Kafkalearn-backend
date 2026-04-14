"""
app/modules/users/schemas/responses.py
=======================================
Pydantic v2 response schemas for the users module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


# ---------------------------------------------------------------------------
# Auth responses
# ---------------------------------------------------------------------------

class AuthResponse(BaseModel):
    """Tokens and user data returned after successful login / registration."""

    access_token: str = Field(
        ...,
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
        description="JWT access token.",
    )
    refresh_token: str = Field(
        ...,
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
        description="JWT refresh token.",
    )
    token_type: str = Field(
        default="bearer",
        examples=["bearer"],
        description="Type de token (toujours 'bearer').",
    )
    user: dict = Field(
        ...,
        examples=[
            {
                "id": 1,
                "email": "eleve@example.com",
                "prenom": "Jean",
                "est_verified": True,
            }
        ],
        description="Donnees de l'utilisateur connecte.",
    )


# ---------------------------------------------------------------------------
# Profile responses
# ---------------------------------------------------------------------------

class UserProfileResponse(BaseModel):
    """Complete profile information for a user."""

    id: str = Field(..., examples=["e17a3699-01a1-43ae-953c-335ea8ba42ef"], description="Identifiant UUID de l'utilisateur.")
    email: str = Field(..., examples=["eleve@example.com"], description="Adresse e-mail.")
    prenom: str | None = Field(None, examples=["Jean"], description="Prenom.")
    nom: str | None = Field(None, examples=["Dupont"], description="Nom de famille.")
    phone: str | None = Field(None, examples=["+237 6 12 34 56 78"], description="Telephone.")
    classe: str | None = Field(None, examples=["Terminale C"], description="Classe.")
    serie: str | None = Field(None, examples=["C"], description="Serie scolaire.")
    region: str | None = Field(None, examples=["Centre"], description="Region.")
    etablissement: str | None = Field(
        None, examples=["Lycee Leclerc"], description="Etablissement scolaire."
    )
    photo_url: str | None = Field(
        None, examples=["https://storage.example.com/photos/1.jpg"], description="Photo de profil."
    )
    langue: str | None = Field(None, examples=["fr"], description="Langue prefer.")
    email_verified: bool = Field(default=False, examples=[True], description="Compte verifie ou non.")
    is_active: bool = Field(default=True, examples=[True], description="Compte actif ou suspendu.")
    created_at: datetime | None = Field(
        default=None, examples=["2025-01-15T08:30:00Z"], description="Date de creation."
    )

    # --- Learning profile summary (aggregated) ---
    streak_jours: int = Field(
        default=0, examples=[7], description="Jours consecutifs d'affilee."
    )
    streak_max: int = Field(
        default=0, examples=[21], description="Record de jours consecutifs."
    )
    score_global: float = Field(
        default=0.0, examples=[78.5], ge=0, le=100, description="Score global en pourcentage."
    )
    total_sessions_etude: int = Field(
        default=0, examples=[42], description="Nombre total de sessions d'etude."
    )
    total_heures_etude: float = Field(
        default=0.0, examples=[15.5], description="Heures totales d'etude."
    )
    nb_quiz_reussis: int = Field(
        default=0, examples=[30], description="Nombre de quizzes reussis."
    )
    learning_profile: dict | None = Field(
        default=None,
        description="Profil d'apprentissage complet agrégé.",
    )


class ProfileStatsResponse(BaseModel):
    """Detailed learning statistics for the authenticated user."""

    streak_jours: int = Field(
        default=0, examples=[7], description="Jours consecutifs actuels."
    )
    streak_max: int = Field(
        default=0, examples=[21], description="Record personnel de jours consecutifs."
    )
    score_global: float = Field(
        default=0.0,
        ge=0,
        le=100,
        examples=[78.5],
        description="Score global moyen en pourcentage.",
    )
    total_sessions_etude: int = Field(
        default=0, examples=[42], description="Nombre total de sessions terminees."
    )
    total_heures_etude: float = Field(
        default=0.0, examples=[15.5], description="Heures totales passees sur la plateforme."
    )
    nb_quiz_reussis: int = Field(
        default=0, examples=[30], description="Quiz reussis (score >= seuil de reussite)."
    )
    nb_quiz_echoues: int = Field(
        default=0, examples=[10], description="Nombre total de quizzes echoues."
    )
    derniere_activite: datetime | None = Field(
        None,
        examples=["2025-04-09T18:00:00Z"],
        description="Date de la derniere activite.",
    )


# ---------------------------------------------------------------------------
# Generic / utility responses
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    """Simple acknowledgement response."""

    message: str = Field(
        ...,
        examples=["Operation effectuee avec succes."],
        description="Message descriptif du resultat.",
    )
    code: str = Field(
        default="ok",
        examples=["ok", "password_reset_sent", "verification_required"],
        description="Code machine pour identification programmatique.",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T] = Field(
        default_factory=list,
        description="Liste des elements de la page courante.",
    )
    total: int = Field(
        ...,
        ge=0,
        examples=[150],
        description="Nombre total d'elements (toutes pages confondues).",
    )
    page: int = Field(
        ...,
        ge=1,
        examples=[1],
        description="Numero de la page courante (basee sur 1).",
    )
    per_page: int = Field(
        ...,
        ge=1,
        le=100,
        examples=[20],
        description="Nombre d'elements par page.",
    )

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        if self.per_page <= 0:
            return 0
        return (self.total + self.per_page - 1) // self.per_page


class ReportStatusResponse(BaseModel):
    """Status of an asynchronously generated report."""

    report_id: str = Field(
        ...,
        examples=["rpt_abc123def456"],
        description="Identifiant unique du rapport.",
    )
    status: str = Field(
        ...,
        examples=["pending", "processing", "completed", "failed"],
        description="Etat actuel du rapport.",
    )
    created_at: datetime = Field(
        ...,
        examples=["2025-04-01T10:00:00Z"],
        description="Date de creation de la demande.",
    )
    completed_at: datetime | None = Field(
        None,
        examples=["2025-04-01T10:05:30Z"],
        description="Date de fin de generation (null si en cours).",
    )
    pdf_url: str | None = Field(
        None,
        examples=["https://storage.example.com/reports/rpt_abc123def456.pdf"],
        description="URL de telechargement du PDF (disponible quand status='completed').",
    )
    error_message: str | None = Field(
        None,
        examples=["Erreur lors de la generation du rapport."],
        description="Message d'erreur si status='failed'.",
    )
