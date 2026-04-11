"""
app/modules/users/schemas/requests.py
======================================
Pydantic v2 request schemas for the users module.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Auth & registration
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    """Payload to register a new user account."""

    email: EmailStr = Field(
        ...,
        examples=["eleve@example.com"],
        description="Adresse e-mail de l'utilisateur.",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        examples=["MonMotDePasse123!"],
        description="Mot de passe (8-128 caracteres).",
    )
    prenom: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        examples=["Jean"],
        description="Prenom de l'utilisateur.",
    )
    langue: str | None = Field(
        None,
        max_length=5,
        examples=["fr"],
        description="Code langue prefer (ex. 'fr', 'en').",
    )
    referral_code: str | None = Field(
        None,
        max_length=32,
        examples=["REF-ABC123"],
        description="Code de parrainage optionnel.",
    )

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins une lettre majuscule.")
        if not any(c.islower() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins une lettre minuscule.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre.")
        return v


class LoginRequest(BaseModel):
    """Payload to authenticate and obtain tokens."""

    email: EmailStr = Field(
        ...,
        examples=["eleve@example.com"],
        description="Adresse e-mail enregistree.",
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        examples=["MonMotDePasse123!"],
        description="Mot de passe du compte.",
    )


class VerifyRequest(BaseModel):
    """Payload to verify an account with a one-time code."""

    email: EmailStr = Field(
        ...,
        examples=["eleve@example.com"],
        description="Adresse e-mail a verifier.",
    )
    code: str = Field(
        ...,
        min_length=4,
        max_length=10,
        examples=["123456"],
        description="Code de verification recu par e-mail.",
    )


class RefreshTokenRequest(BaseModel):
    """Payload to exchange a refresh token for a new access token."""

    refresh_token: str = Field(
        ...,
        examples=["eyJhbGciOiJIUzI1NiIs..."],
        description="Refresh token obtenu lors de la connexion.",
    )


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------

class PasswordResetRequest(BaseModel):
    """Request to trigger a password-reset e-mail."""

    email: EmailStr = Field(
        ...,
        examples=["eleve@example.com"],
        description="Adresse e-mail du compte a recuperer.",
    )


class PasswordChangeRequest(BaseModel):
    """Payload to change the password of an authenticated user."""

    old_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        examples=["AncienMotDePasse1!"],
        description="Mot de passe actuel.",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        examples=["NouveauMotDePasse456!"],
        description="Nouveau mot de passe (8-128 caracteres).",
    )

    @field_validator("new_password")
    @classmethod
    def new_password_must_be_strong(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins une lettre majuscule.")
        if not any(c.islower() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins une lettre minuscule.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Le mot de passe doit contenir au moins un chiffre.")
        return v


# ---------------------------------------------------------------------------
# Profile & onboarding
# ---------------------------------------------------------------------------

class ProfileUpdateRequest(BaseModel):
    """Partial update of the authenticated user's profile. All fields optional."""

    prenom: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        examples=["Jean"],
        description="Prenom de l'utilisateur.",
    )
    nom: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        examples=["Dupont"],
        description="Nom de famille.",
    )
    phone: str | None = Field(
        None,
        max_length=20,
        examples=["+237 6 12 34 56 78"],
        description="Numero de telephone.",
    )
    classe: str | None = Field(
        None,
        max_length=50,
        examples=["Terminale C"],
        description="Classe actuelle de l'eleve.",
    )
    serie: str | None = Field(
        None,
        max_length=20,
        examples=["C", "D", "A", "TI"],
        description="Serie scolaire (C, D, A, TI, etc.).",
    )
    region: str | None = Field(
        None,
        max_length=80,
        examples=["Centre", "Littoral"],
        description="Region de residence.",
    )
    etablissement: str | None = Field(
        None,
        max_length=150,
        examples=["Lycee Leclerc"],
        description="Nom de l'etablissement scolaire.",
    )
    photo_url: str | None = Field(
        None,
        max_length=500,
        examples=["https://storage.example.com/photos/user123.jpg"],
        description="URL de la photo de profil.",
    )


class OnboardingCompleteRequest(BaseModel):
    """Payload to complete the onboarding questionnaire."""

    classe: str = Field(
        ...,
        max_length=50,
        examples=["Terminale C"],
        description="Classe de l'eleve.",
    )
    serie: str = Field(
        ...,
        max_length=20,
        examples=["C"],
        description="Serie scolaire choisie.",
    )
    langue: str = Field(
        ...,
        max_length=5,
        examples=["fr"],
        description="Langue d'enseignement prefer (ex. 'fr', 'en').",
    )
    matiere_forte: str | None = Field(
        None,
        max_length=80,
        examples=["Mathematiques"],
        description="Matiere dans laquelle l'eleve excelle.",
    )
    matiere_faible: str | None = Field(
        None,
        max_length=80,
        examples=["Physique"],
        description="Matiere dans laquelle l'eleve a des difficultes.",
    )
