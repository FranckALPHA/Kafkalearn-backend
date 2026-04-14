"""
routes/auth.py
==============
Endpoints d'authentification : register, login, verify, password reset.
"""
import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.modules.users.schemas.requests import (
    UserRegisterRequest,
    LoginRequest,
    VerifyRequest,
    PasswordResetRequest,
    PasswordResetVerifyRequest,
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
from app.modules.users.utils.security import generate_fingerprint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _raise_auth_http_error(code: str) -> None:
    mapping = {
        "USER_ALREADY_EXISTS": (status.HTTP_409_CONFLICT, code),
        "USER_NOT_FOUND": (status.HTTP_404_NOT_FOUND, code),
        "USER_ALREADY_VERIFIED": (status.HTTP_400_BAD_REQUEST, code),
        "INVALID_OR_EXPIRED_OTP": (status.HTTP_400_BAD_REQUEST, code),
        "INVALID_CREDENTIALS": (status.HTTP_401_UNAUTHORIZED, code),
        "EMAIL_NOT_VERIFIED": (status.HTTP_403_FORBIDDEN, code),
        "ACCOUNT_DISABLED": (status.HTTP_403_FORBIDDEN, code),
        "INVALID_REFRESH_TOKEN": (status.HTTP_401_UNAUTHORIZED, code),
        "REFRESH_TOKEN_REVOKED": (status.HTTP_401_UNAUTHORIZED, code),
    }
    status_code, detail = mapping.get(code, (status.HTTP_400_BAD_REQUEST, code))
    raise HTTPException(status_code=status_code, detail=detail)


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
    try:
        user_service.inscrire_utilisateur(
            email=payload.email,
            password=payload.password,
            prenom=payload.prenom,
            langue=payload.langue or "fr",
            referral_code=payload.referral_code,
        )
    except ValueError as exc:
        _raise_auth_http_error(str(exc))
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
    try:
        result = user_service.verifier_otp_et_authentifier(
            email=payload.email,
            code=payload.code,
        )
    except ValueError as exc:
        _raise_auth_http_error(str(exc))
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
    try:
        result = user_service.authentifier(
            email=payload.email,
            password=payload.password,
            fingerprint=fingerprint,
        )
    except ValueError as exc:
        _raise_auth_http_error(str(exc))
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
    user_service.logout(user_id=str(current_user.id))
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
    user_service.demander_reset_mot_de_passe(payload.email)
    return MessageResponse(
        message="Si un compte existe avec cet email, vous recevrez un code de réinitialisation.",
        code="RESET_REQUESTED",
    )


@router.post(
    "/password/reset/verify",
    response_model=MessageResponse,
    dependencies=[Depends(get_rate_limiter_dependency(password_reset_rate_limiter))],
)
async def verify_password_reset(
    payload: PasswordResetVerifyRequest,
    user_service=Depends(get_user_service),
):
    """
    Vérifie le code OTP pour la réinitialisation de mot de passe
    et applique le nouveau mot de passe.
    """
    user_service.reinitialiser_mot_de_passe(
        email=payload.email,
        code=payload.code,
        nouveau_mot_de_passe=payload.new_password,
    )
    return MessageResponse(
        message="Mot de passe réinitialisé avec succès. Veuillez vous reconnecter.",
        code="PASSWORD_RESET_SUCCESS",
    )


@router.post("/password/change", response_model=MessageResponse)
async def change_password(
    payload: PasswordChangeRequest,
    current_user=Depends(get_current_user),
    user_service=Depends(get_user_service),
):
    """Changement de mot de passe (nécessite l'ancien)."""
    user_service.changer_mot_de_passe(
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
    try:
        result = user_service.refresh_access_token(
            refresh_token=payload.refresh_token,
            fingerprint=fingerprint,
        )
    except ValueError as exc:
        _raise_auth_http_error(str(exc))
    return AuthResponse(**result)
