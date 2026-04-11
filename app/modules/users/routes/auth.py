"""
routes/auth.py
==============
Endpoints d'authentification : register, login, verify, password reset.
"""
import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.modules.users.schemas.requests import (
    UserRegisterRequest,
    LoginRequest,
    VerifyRequest,
    PasswordResetRequest,
    PasswordChangeRequest,
    RefreshTokenRequest,
)
from app.modules.users.schemas.responses import AuthResponse, MessageResponse
from app.modules.users.routes.dependencies import (
    get_db,
    get_user_service,
    get_rate_limiter_dependency,
    get_current_user,
)
from app.modules.users.utils.rate_limiter import (
    register_rate_limiter,
    auth_rate_limiter,
    password_reset_rate_limiter,
)
from app.modules.users.utils.security import generate_fingerprint, decode_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=201,
    dependencies=[Depends(get_rate_limiter_dependency(register_rate_limiter))],
)
async def register(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
    user_service=Depends(get_user_service),
):
    """
    Inscription d'un nouvel utilisateur.
    Limite : 3 requêtes/minute par IP.
    Un code OTP est envoyé par email.
    """
    result = await user_service.inscrire_utilisateur(
        email=payload.email,
        password=payload.password,
        prenom=payload.prenom,
        langue=payload.langue or "fr",
        referral_code=payload.referral_code,
    )
    return MessageResponse(
        message="Inscription réussie. Vérifiez votre email pour activer votre compte.",
        code="REGISTER_SUCCESS",
    )


@router.post(
    "/verify",
    response_model=AuthResponse,
    dependencies=[Depends(get_rate_limiter_dependency(auth_rate_limiter))],
)
async def verify_email(
    payload: VerifyRequest,
    user_service=Depends(get_user_service),
):
    """
    Vérification du code OTP envoyé par email.
    Retourne les tokens d'accès après vérification.
    """
    result = await user_service.verifier_otp_et_authentifier(
        email=payload.email,
        code=payload.code,
    )
    return AuthResponse(**result)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(get_rate_limiter_dependency(auth_rate_limiter))],
)
async def login(
    request: Request,
    payload: LoginRequest,
    user_service=Depends(get_user_service),
):
    """
    Connexion avec email/mot de passe.
    Limite : 5 requêtes/minute par IP + fingerprint device.
    """
    fingerprint = generate_fingerprint(
        request.headers.get("x-forwarded-for") or request.client.host,
        request.headers.get("user-agent", ""),
    )
    result = await user_service.authentifier(
        email=payload.email,
        password=payload.password,
        fingerprint=fingerprint,
    )
    return AuthResponse(**result)


@router.post(
    "/logout",
    response_model=MessageResponse,
)
async def logout(
    current_user=Depends(get_current_user),
    user_service=Depends(get_user_service),
):
    """Déconnexion : révoque tous les refresh tokens."""
    await user_service.logout(user_id=str(current_user.id))
    return MessageResponse(message="Déconnexion réussie", code="LOGOUT_SUCCESS")


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    dependencies=[Depends(get_rate_limiter_dependency(password_reset_rate_limiter))],
)
async def request_password_reset(
    payload: PasswordResetRequest,
    user_service=Depends(get_user_service),
):
    """
    Demande de réinitialisation de mot de passe.
    Envoie un code OTP par email.
    Limite : 3 requêtes/5 minutes par IP.
    """
    # TODO: Implement password reset request flow
    return MessageResponse(
        message="Si un compte existe avec cet email, vous recevrez un code de réinitialisation.",
        code="RESET_REQUESTED",
    )


@router.post("/password/change", response_model=MessageResponse)
async def change_password(
    payload: PasswordChangeRequest,
    current_user=Depends(get_current_user),
    user_service=Depends(get_user_service),
):
    """Changement de mot de passe (nécessite l'ancien)."""
    await user_service.changer_mot_de_passe(
        user_id=str(current_user.id),
        old_password=payload.old_password,
        new_password=payload.new_password,
    )
    return MessageResponse(
        message="Mot de passe modifié avec succès",
        code="PASSWORD_CHANGED",
    )


@router.post("/token/refresh", response_model=AuthResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    user_service=Depends(get_user_service),
):
    """
    Rafraîchit le token d'accès avec un refresh token valide.
    Vérifie le fingerprint device.
    """
    fingerprint = generate_fingerprint(
        request.headers.get("x-forwarded-for") or request.client.host,
        request.headers.get("user-agent", ""),
    )
    result = await user_service.refresh_access_token(
        refresh_token=payload.refresh_token,
        fingerprint=fingerprint,
    )
    return AuthResponse(**result)
