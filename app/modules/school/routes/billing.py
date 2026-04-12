"""
routes/billing.py
=================
Facturation et renouvellement d'abonnement école.
"""
import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from app.modules.school.routes.dependencies import (
    get_current_user,
    get_db,
    require_school_admin,
    get_school_service,
)
from app.modules.school.utils.pricing_calculator import PricingCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/school/billing", tags=["School Billing"])


@router.get("/")
async def get_billing_info(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Récupère les informations de facturation et d'expiration (admin uniquement)."""
    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    require_school_admin(school_id=current_user.school_id, current_user=current_user, db=db)

    from app.modules.school.models import School

    school = db.query(School).filter(School.id == current_user.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="SCHOOL_NOT_FOUND")

    jours_restants = school.jours_restants
    pricing = PricingCalculator()
    prix_mensuel = pricing.calculer_prix_mensuel(school.nb_eleves_max)

    return {
        "school_id": school.id,
        "nom": school.nom,
        "nb_eleves_max": school.nb_eleves_max,
        "date_expiration": school.date_expiration.isoformat() if school.date_expiration else None,
        "jours_restants": jours_restants,
        "is_active": school.is_active,
        "is_trial": school.is_trial,
        "tarif_mensuel_fcfa": prix_mensuel,
        "renewal_options": {
            "renouvellement_30j": f"{prix_mensuel:,} FCFA" if prix_mensuel else "Sur devis",
        },
    }


@router.post("/renew")
async def renew_school(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Initier le renouvellement de l'école (admin uniquement). Retourne un lien de paiement."""
    if not current_user.school_id:
        raise HTTPException(status_code=404, detail="NOT_IN_SCHOOL")

    require_school_admin(school_id=current_user.school_id, current_user=current_user, db=db)

    from app.modules.school.models import School

    school = db.query(School).filter(School.id == current_user.school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="SCHOOL_NOT_FOUND")

    pricing = PricingCalculator()
    montant = pricing.calculer_prix_mensuel(school.nb_eleves_max)

    # Intégration avec PaymentService pour initier le paiement NotchPay
    try:
        from app.modules.payment.services.payment_service import PaymentService
        payment_service = PaymentService(db)
        payment_result = await payment_service.initier_paiement_ecole(
            admin_user=current_user,
            school_id=school.id,
            nb_sieges=school.nb_eleves_max,
            callback_url=f"{request.base_url}payment/callback",
        )
        return {
            "message": "Redirection vers le paiement NotchPay",
            "montant_fcfa": montant,
            "nb_sieges": school.nb_eleves_max,
            "authorization_url": payment_result.get("authorization_url"),
        }
    except ImportError:
        # Payment module non disponible
        pass

    return {
        "message": "Renouvellement initié. Redirection vers le paiement.",
        "montant_fcfa": montant,
        "nb_sieges": school.nb_eleves_max,
    }
