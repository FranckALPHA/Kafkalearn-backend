"""
routes/payments.py
==================
Endpoints payment utilisateur : plans, checkout, callback, history, status.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.modules.payment.schemas.responses import (
    CheckoutResponse,
    PlanListResponse,
    SubscriptionStatusResponse,
    TransactionHistoryResponse,
)
from app.modules.payment.routes.dependencies import (
    get_db,
    get_current_user,
    get_optional_user,
    require_email_verified,
    get_payment_checkout_rate_limiter,
    get_payment_service,
)
from app.modules.payment.services import PaymentService
from app.modules.payment.models import PlanPrice, Transaction
from app.modules.users.models import User
from app.modules.skills.models import SkillUsageLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment", tags=["payment"])


# ─── GET /payment/plans ────────────────────────────────────────

@router.get("/plans", response_model=PlanListResponse)
async def list_plans(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    """Liste tous les plans disponibles avec indication du plan courant."""
    plans = db.query(PlanPrice).filter(PlanPrice.is_active == True).order_by(PlanPrice.prix_fcfa).all()

    user_plan = user.plan_effectif if user else None

    plan_list = []
    for plan in plans:
        serialized = plan.serialize_for_api()
        serialized["is_current"] = (plan.plan_id == user_plan)
        plan_list.append(serialized)

    return PlanListResponse(plans=plan_list, devise="FCFA")


# ─── POST /payment/checkout/{plan_id} ─────────────────────────

@router.post("/checkout/{plan_id}", response_model=CheckoutResponse)
async def checkout_plan(
    plan_id: str,
    request: Request,
    current_user: User = Depends(require_email_verified),
    _rate_limit: bool = Depends(get_payment_checkout_rate_limiter),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """Initie un paiement NotchPay pour le plan specifie. Requiert email verifie."""
    try:
        result = await payment_service.initier_paiement(
            user=current_user,
            plan_id=plan_id,
        )
        return CheckoutResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Checkout error for user {current_user.id}, plan {plan_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PAYMENT_INIT_FAILED",
        )


# ─── GET /payment/callback ─────────────────────────────────────

@router.get("/callback")
async def payment_callback(
    request: Request,
    reference: str = Query(..., description="Reference de transaction"),
    db: Session = Depends(get_db),
):
    """Callback apres paiement — redirige vers le frontend avec le statut."""
    from app.core.config import FRONTEND_URL

    transaction = (
        db.query(Transaction)
        .filter(Transaction.gateway_ref == reference)
        .first()
    )

    if not transaction:
        redirect_url = f"{FRONTEND_URL}/payment?status=not_found&ref={reference}"
        return RedirectResponse(url=redirect_url)

    status_map = {
        "complete": "success",
        "pending": "pending",
        "failed": "failed",
        "canceled": "cancelled",
        "processing": "pending",
    }

    ui_status = status_map.get(transaction.status, "unknown")
    redirect_url = f"{FRONTEND_URL}/payment?status={ui_status}&ref={reference}"
    return RedirectResponse(url=redirect_url)


# ─── GET /payment/history ──────────────────────────────────────

@router.get("/history", response_model=TransactionHistoryResponse)
async def transaction_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Historique des transactions de l'utilisateur connecte."""
    offset = (page - 1) * limit

    total_query = (
        db.query(sa_func.count(Transaction.id))
        .filter(Transaction.user_id == current_user.id)
    )
    total = total_query.scalar() or 0

    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    serialized = [t.serialize_for_history() for t in transactions]

    return TransactionHistoryResponse(
        total=total,
        page=page,
        limit=limit,
        transactions=serialized,
    )


# ─── GET /payment/status ───────────────────────────────────────

@router.get("/status", response_model=SubscriptionStatusResponse)
async def subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Statut d'abonnement actuel de l'utilisateur avec quota et jours restants."""
    plan_base = current_user.plan_base or "freemium"
    plan_effectif = current_user.plan_effectif or "freemium"
    plan_expiration_at = current_user.plan_expiration_at

    # Calcul des jours restants
    if plan_expiration_at:
        now = datetime.utcnow()
        expiration = plan_expiration_at if plan_expiration_at.tzinfo is None else plan_expiration_at.replace(tzinfo=None)
        jours_restants = max(0, (expiration - now).days)
    else:
        jours_restants = 0 if plan_effectif == "freemium" else 999

    # Quota IA
    quota_ia = {
        "plan": plan_effectif,
        "used": 0,
        "limit": 0,
        "type": "monthly",
    }

    # Recuperer les infos du plan pour le quota
    plan_price = db.query(PlanPrice).filter(PlanPrice.plan_id == plan_effectif).first()
    if plan_price:
        quota_ia["limit"] = plan_price.quota_valeur
        quota_ia["type"] = plan_price.quota_type

        # Compter les utilisations IA reelles depuis la table skill_usage_logs
        now = datetime.utcnow()
        if plan_price.quota_type == "monthly":
            period_start = now - timedelta(days=30)
        elif plan_price.quota_type == "daily":
            period_start = now - timedelta(days=1)
        elif plan_price.quota_type == "yearly":
            period_start = now - timedelta(days=365)
        else:
            period_start = now - timedelta(days=30)  # default monthly

        quota_ia["used"] = (
            db.query(SkillUsageLog)
            .filter(
                SkillUsageLog.user_id == current_user.id,
                SkillUsageLog.created_at >= period_start,
                SkillUsageLog.quota_consomme == True,
            )
            .count()
        )

    # Auto-renew: verificar s'il y a une transaction recente pour ce plan
    recent_complete = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.status == "complete",
            Transaction.type == "payment",
            Transaction.plan_id == plan_effectif,
            Transaction.created_at >= datetime.utcnow() - timedelta(days=30),
        )
        .first()
    )
    auto_renew = recent_complete is not None

    return SubscriptionStatusResponse(
        plan_base=plan_base,
        plan_effectif=plan_effectif,
        plan_expiration_at=plan_expiration_at.isoformat() if plan_expiration_at else None,
        jours_restants=jours_restants,
        quota_ia=quota_ia,
        auto_renew=auto_renew,
        source="payment_direct",
    )
