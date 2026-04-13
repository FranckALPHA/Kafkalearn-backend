"""
routes/admin.py
===============
Endpoints admin pour la supervision des paiements.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.modules.payment.routes.dependencies import (
    get_db,
    get_current_user,
    get_analytics_service,
    get_payment_service,
)
from app.modules.payment.services import PaymentAnalyticsService, PaymentService
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/payment", tags=["admin-payment"])


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Verifie que l'utilisateur est admin ou superadmin.
    
    NOTE: Disabled for development phase - any user can access.
    """
    # DEV MODE: Allow any user
    return current_user
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="INSUFFICIENT_PERMISSIONS",
        )
    return current_user


# ─── GET /admin/payment/analytics ──────────────────────────────

@router.get("/analytics")
async def payment_analytics(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    analytics_service: PaymentAnalyticsService = Depends(get_analytics_service),
):
    """Statistiques paiement : MRR, taux de conversion, transactions en attente."""
    mrr_data = await analytics_service.calculer_mrr()
    conversion_rate = await analytics_service.taux_conversion_freemium()
    pending = await analytics_service.transactions_pending_trop_longtemps()

    return {
        "mrr": mrr_data,
        "conversion_rate_freemium": conversion_rate,
        "pending_count": len(pending),
    }


# ─── GET /admin/payment/pending ────────────────────────────────

@router.get("/pending")
async def list_pending_transactions(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    analytics_service: PaymentAnalyticsService = Depends(get_analytics_service),
):
    """Liste les transactions bloquees en attente depuis plus de 2h."""
    pending = await analytics_service.transactions_pending_trop_longtemps(heures_seuil=2)
    return {"pending": pending, "total": len(pending)}


# ─── POST /admin/payment/retry/{reference} ─────────────────────

@router.post("/retry/{reference}")
async def retry_pending_transaction(
    reference: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """Relance manuelle de verification d'une transaction en attente."""
    try:
        result = await payment_service.verifier_transaction(reference)
        return {"status": "retry_completed", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Admin retry failed for {reference}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RETRY_FAILED",
        )
