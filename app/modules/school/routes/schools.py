"""
routes/schools.py
=================
Endpoints principaux pour la gestion des écoles.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse

from app.modules.school.schemas.requests import SchoolCreateRequest, SchoolJoinRequest
from app.modules.school.schemas.responses import SchoolDashboardResponse, PricingResponse
from app.modules.school.routes.dependencies import (
    get_current_user,
    forbid_already_in_school,
    get_rate_limiter_dependency,
    school_create_rate_limiter,
    school_join_rate_limiter,
    school_delete_rate_limiter,
    get_school_service,
)
from app.modules.school.utils.pricing_calculator import PricingCalculator
from app.modules.school.utils.constants import SCHOOL_TRIAL_DAYS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/school", tags=["School"])


@router.post(
    "/creer",
    response_model=SchoolDashboardResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_rate_limiter_dependency(school_create_rate_limiter))],
)
async def creer_ecole(
    body: SchoolCreateRequest,
    current_user=Depends(forbid_already_in_school),
    school_service=Depends(get_school_service),
):
    """Créer une nouvelle école avec période d'essai de 30 jours. Email vérifié requis."""
    if not getattr(current_user, "email_verified", False):
        raise HTTPException(status_code=403, detail="EMAIL_NOT_VERIFIED")

    result = await school_service.creer_ecole(
        admin_user=current_user,
        nom=body.nom,
        ville=body.ville,
        pays=body.pays or "CM",
        region=body.region,
        nb_sieges=body.nb_sieges,
        description=body.description,
    )
    return result


@router.post(
    "/rejoindre",
    dependencies=[Depends(get_rate_limiter_dependency(school_join_rate_limiter))],
)
async def rejoindre_ecole(
    body: SchoolJoinRequest,
    current_user=Depends(forbid_already_in_school),
    school_service=Depends(get_school_service),
):
    """Rejoindre une école via un code d'invitation."""
    result = await school_service.rejoindre_par_code(
        user=current_user,
        code=body.code,
    )
    return result


@router.get("/dashboard", response_model=SchoolDashboardResponse)
async def get_dashboard(
    current_user=Depends(get_current_user),
    school_service=Depends(get_school_service),
):
    """Récupère le tableau de bord de l'école de l'utilisateur."""
    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    from app.modules.school.models import School

    # Vérification école active via DB
    school = school_service.db.query(School).filter(
        School.id == current_user.school_id,
        School.is_active == True,
    ).first()
    if not school:
        raise HTTPException(status_code=402, detail="SCHOOL_EXPIRED")

    # Vérification si admin
    from app.modules.school.models import SchoolMember

    is_admin = (
        school_service.db.query(SchoolMember)
        .filter(
            SchoolMember.school_id == current_user.school_id,
            SchoolMember.user_id == current_user.id,
            SchoolMember.role_ecole == "admin",
            SchoolMember.is_active == True,
        )
        .first()
        is not None
    )

    dashboard = await school_service.recuperer_dashboard(
        school_id=current_user.school_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
    return dashboard


@router.get("/tarifs", response_model=PricingResponse)
async def get_tarifs():
    """Grille tarifaire publique (aucune auth requise)."""
    pricing = PricingCalculator()
    tarifs = []
    for min_s, max_s, prix in pricing.TIERS:
        tarifs.append(
            {
                "tranche": f"{min_s}-{max_s if max_s else '+'}",
                "nb_sieges_min": min_s,
                "nb_sieges_max": max_s,
                "prix_par_siege_fcfa": prix,
                "exemple": pricing.get_exemple_tarif(min_s),
            }
        )
    return PricingResponse(tarifs=tarifs, essai_gratuit_jours=SCHOOL_TRIAL_DAYS, devise="FCFA (XAF)")


@router.delete(
    "/supprimer",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_rate_limiter_dependency(school_delete_rate_limiter))],
)
async def supprimer_ecole(
    request: Request,
    current_user=Depends(get_current_user),
    school_service=Depends(get_school_service),
):
    """Supprimer l'école entière. Confirmation texte requise (admin uniquement)."""
    body = await request.json()
    confirmation = body.get("confirmation", "")

    if confirmation != "SUPPRIMER":
        raise HTTPException(status_code=400, detail="CONFIRMATION_REQUIRED")

    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    await school_service.supprimer_ecole(
        school_id=current_user.school_id,
        admin_id=current_user.id,
        confirmation=confirmation,
    )
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
