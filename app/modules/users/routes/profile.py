"""
routes/profile.py
=================
Endpoints de gestion du profil utilisateur.
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.modules.users.schemas.responses import (
    UserProfileResponse,
    ProfileStatsResponse,
    MessageResponse,
)
from app.modules.users.schemas.requests import ProfileUpdateRequest, OnboardingCompleteRequest
from app.modules.users.routes.dependencies import (
    get_db,
    get_current_user,
    get_user_service,
    get_learning_profile_service,
    get_streak_service,
    get_audit_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    profile_service=Depends(get_learning_profile_service),
):
    """Retourne le profil complet de l'utilisateur connecté."""
    profile_data = await profile_service.obtenir_profil_complet(user_id=str(current_user.id))
    return UserProfileResponse(
        **current_user.serialize_minimal(),
        learning_profile=profile_data,
    )


@router.put("/me", response_model=MessageResponse)
async def update_my_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    user_service=Depends(get_user_service),
):
    """Met à jour les informations du profil."""
    await user_service.mettre_a_jour_profil(
        user_id=str(current_user.id),
        payload_dict=payload.model_dump(exclude_unset=True),
    )
    return MessageResponse(message="Profil mis à jour", code="PROFILE_UPDATED")


@router.post("/onboarding", response_model=MessageResponse)
async def complete_onboarding(
    payload: OnboardingCompleteRequest,
    current_user: User = Depends(get_current_user),
    user_service=Depends(get_user_service),
):
    """
    Complète l'onboarding : classe, série, langue, préférences.
    Une seule fois (après, contact support pour modification).
    """
    await user_service.mettre_a_jour_profil(
        user_id=str(current_user.id),
        payload_dict={
            "classe": payload.classe,
            "serie": payload.serie,
            "langue": payload.langue,
            "matiere_forte": payload.matiere_forte,
            "matiere_faible": payload.matiere_faible,
            "onboarding_completed": True,
        },
    )
    return MessageResponse(
        message="Onboarding terminé avec succès !",
        code="ONBOARDING_COMPLETED",
    )


@router.get("/me/stats", response_model=ProfileStatsResponse)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    streak_service=Depends(get_streak_service),
):
    """Retourne les statistiques détaillées de l'utilisateur."""
    streak_service.calculer_streak(str(current_user.id))

    return ProfileStatsResponse(
        streak_jours=current_user.streak_jours,
        streak_max=current_user.streak_max,
        score_global=current_user.score_global,
        progression_hebdo=current_user.progression_hebdo,
        total_sessions_etude=current_user.total_sessions_etude,
        total_heures_etude=current_user.total_heures_etude,
        nb_quiz_reussis=current_user.nb_quiz_reussis,
        nb_quiz_echoues=current_user.nb_quiz_echoues,
        derniere_activite=current_user.derniere_activite_at,
    )


@router.get("/me/activity")
async def get_my_activity(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    audit_service=Depends(get_audit_service),
):
    """Retourne les dernières activités de l'utilisateur."""
    logs = audit_service.get_user_audit_log(user_id=str(current_user.id), limit=limit)
    return {"activities": logs, "total": len(logs)}
