"""
services/payment_analytics_service.py
=====================================
Service d'analytiques pour les paiements et abonnements.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from redis import Redis
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.modules.payment.models import Transaction
from app.modules.payment.services.base import PaymentBaseService

logger = logging.getLogger(__name__)


class PaymentAnalyticsService(PaymentBaseService):
    """Service d'analytiques paiement."""

    async def calculer_mrr(self, reference_date: datetime = None) -> Dict[str, Any]:
        """Calcule le MRR (Monthly Recurring Revenue) par plan."""
        cache_key = "analytics:mrr"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        ref_date = reference_date or datetime.utcnow()

        results = (
            self.db.query(
                Transaction.plan_id,
                sa_func.count(Transaction.user_id).label("nb_users"),
                sa_func.sum(Transaction.amount).label("total_revenu"),
            )
            .filter(
                Transaction.status == "complete",
                Transaction.type == "payment",
                Transaction.plan_id != "freemium",
                Transaction.created_at >= ref_date - timedelta(days=30),
            )
            .group_by(Transaction.plan_id)
            .all()
        )

        mrr_by_plan = {}
        total_mrr = 0
        for row in results:
            plan_id = row.plan_id
            nb = row.nb_users or 0
            revenu = row.total_revenu or 0
            mrr_by_plan[plan_id] = {"nb_users": nb, "revenu": revenu}
            total_mrr += revenu

        result = {"total_mrr": total_mrr, "by_plan": mrr_by_plan}

        # Cache 24h
        self.redis.setex(cache_key, 86400, json.dumps(result))
        return result

    async def taux_conversion_freemium(self, periode_jours: int = 30) -> float:
        """Calcule le taux de conversion freemium -> payant."""
        cutoff = datetime.utcnow() - timedelta(days=periode_jours)

        freemium_count = (
            self.db.query(sa_func.count())
            .select_from(Transaction)
            .filter(
                Transaction.created_at >= cutoff,
                Transaction.plan_precedent == "freemium",
                Transaction.type == "payment",
            )
            .scalar()
        ) or 0

        converted_count = (
            self.db.query(sa_func.count())
            .select_from(Transaction)
            .filter(
                Transaction.created_at >= cutoff,
                Transaction.plan_precedent == "freemium",
                Transaction.type == "payment",
                Transaction.status == "complete",
            )
            .scalar()
        ) or 0

        if freemium_count == 0:
            return 0.0

        return round(converted_count / freemium_count * 100, 2)

    async def transactions_pending_trop_longtemps(self, heures_seuil: int = 2) -> List[Dict[str, Any]]:
        """Retourne les transactions en attente depuis plus de N heures."""
        cutoff = datetime.utcnow() - timedelta(hours=heures_seuil)

        pending = (
            self.db.query(Transaction)
            .filter(
                Transaction.status == "pending",
                Transaction.created_at <= cutoff,
            )
            .order_by(Transaction.created_at)
            .all()
        )

        return [
            {
                "id": t.id,
                "user_id": str(t.user_id),
                "amount": t.amount,
                "plan_id": t.plan_id,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "email_masked": self._mask_email(t.user.email) if t.user else "unknown",
            }
            for t in pending
        ]

    def _mask_email(self, email: str) -> str:
        """Masque partiellement un email pour les logs."""
        if not email or "@" not in email:
            return "***@***.***"
        local, domain = email.split("@", 1)
        masked_local = local[0] + "***" + local[-1] if len(local) > 2 else "***"
        return f"{masked_local}@{domain}"
