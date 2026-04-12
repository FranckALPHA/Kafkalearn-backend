"""
services/payment_service.py
===========================
Service principal pour les operations de paiement.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from redis import Redis
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.payment.models import PlanPrice, Transaction
from app.modules.payment.utils.notchpay_client import NotchPayClient
from app.modules.payment.utils.reference_generator import ReferenceGenerator
from app.modules.payment.utils.constants import PLANS
from app.modules.payment.utils.price_calculator import PriceCalculator
from app.modules.payment.services.base import PaymentBaseService
from app.modules.users.models.user import User
from app.core.config import NOTCH_CALLBACK_URL, NOTCH_PRIVATE_KEY

logger = logging.getLogger(__name__)


class PaymentService(PaymentBaseService):
    """Service de gestion des paiements et abonnements."""

    def __init__(self, db: Session, redis: Redis = None, notchpay_client: NotchPayClient = None):
        super().__init__(db, redis)
        self.notchpay_client = notchpay_client or NotchPayClient()

    async def initier_paiement(
        self,
        user: User,
        plan_id: str,
        callback_url: str = None,
    ) -> Dict[str, Any]:
        """Initialise un paiement pour un utilisateur individuel."""
        if plan_id not in PLANS or plan_id == "freemium":
            raise ValueError(f"Plan invalide: {plan_id}")

        price = PriceCalculator.get_plan_price(plan_id)
        if price is None:
            raise ValueError(f"Prix non defini pour le plan: {plan_id}")

        reference = ReferenceGenerator.generate("individual")
        callback = callback_url or NOTCH_CALLBACK_URL

        try:
            payment_data = await self.notchpay_client.initialize_payment(
                amount=price,
                currency="XAF",
                reference=reference,
                email=user.email,
                callback_url=callback,
                metadata={"user_id": str(user.id), "plan_id": plan_id},
            )
        except Exception as exc:
            logger.error(f"NotchPay initialization failed: {exc}")
            raise

        transaction = Transaction(
            user_id=user.id,
            amount=price,
            currency="XAF",
            plan_id=plan_id,
            plan_precedent=user.plan_effectif,
            type="payment",
            status="pending",
            gateway_ref=reference,
        )
        self.db.add(transaction)
        self.db.commit()

        expires_at = datetime.utcnow() + timedelta(minutes=30)

        return {
            "authorization_url": payment_data.get("authorization_url"),
            "reference": reference,
            "montant": price,
            "currency": "XAF",
            "plan_id": plan_id,
            "expires_at": expires_at.isoformat(),
        }

    async def verifier_transaction(self, reference: str) -> Dict[str, Any]:
        """Verifie le statut d'une transaction via NotchPay."""
        transaction = (
            self.db.query(Transaction)
            .filter(Transaction.gateway_ref == reference)
            .first()
        )
        if not transaction:
            raise ValueError(f"Transaction introuvable: {reference}")

        verification = await self.notchpay_client.verify_payment(reference)
        status_val = verification.get("status", "").lower()

        if status_val in ("success", "completed"):
            transaction.status = "complete"
            transaction.raw_data = verification
            self.db.commit()
            await self.valider_abonnement(transaction)
        elif status_val in ("failed", "cancelled"):
            transaction.status = "failed"
            transaction.raw_data = verification
            self.db.commit()

        return {
            "transaction_id": transaction.id,
            "status": transaction.status,
            "amount": transaction.amount,
            "plan_id": transaction.plan_id,
        }

    async def valider_abonnement(self, transaction: Transaction) -> None:
        """Met a jour le plan de l'utilisateur apres paiement reussi."""
        user = self.db.query(User).filter(User.id == transaction.user_id).first()
        if not user:
            logger.error(f"User {transaction.user_id} not found for transaction {transaction.id}")
            return

        now = func.now()
        user.plan_effectif = transaction.plan_id
        user.plan_expiration_at = now + timedelta(days=30)
        self.db.commit()

        logger.info(
            f"Abonnement valide: user={user.id}, plan={transaction.plan_id}, "
            f"expires_at=+30j"
        )

    async def initier_paiement_ecole(
        self,
        admin_user: User,
        school_id: str,
        nb_sieges: int,
        callback_url: str = None,
    ) -> Dict[str, Any]:
        """Initialise un paiement pour un plan ecole."""
        price = PriceCalculator.calculer_prix_mensuel(nb_sieges)
        if price is None:
            raise ValueError("Custom pricing required for this number of seats")

        reference = ReferenceGenerator.generate("school")
        callback = callback_url or NOTCH_CALLBACK_URL

        try:
            payment_data = await self.notchpay_client.initialize_payment(
                amount=price,
                currency="XAF",
                reference=reference,
                email=admin_user.email,
                callback_url=callback,
                metadata={
                    "user_id": str(admin_user.id),
                    "plan_id": "school",
                    "school_id": school_id,
                    "nb_sieges": nb_sieges,
                },
            )
        except Exception as exc:
            logger.error(f"NotchPay school payment initialization failed: {exc}")
            raise

        transaction = Transaction(
            user_id=admin_user.id,
            amount=price,
            currency="XAF",
            plan_id="school",
            plan_precedent=admin_user.plan_effectif,
            type="payment",
            status="pending",
            gateway_ref=reference,
            school_id=school_id,
            nb_sieges=nb_sieges,
        )
        self.db.add(transaction)
        self.db.commit()

        expires_at = datetime.utcnow() + timedelta(minutes=30)

        return {
            "authorization_url": payment_data.get("authorization_url"),
            "reference": reference,
            "montant": price,
            "currency": "XAF",
            "plan_id": "school",
            "nb_sieges": nb_sieges,
            "expires_at": expires_at.isoformat(),
        }

    def _reactiver_membres_ecole(self, school_id: str) -> None:
        """Reactiver tous les membres d'une ecole avec le plan school."""
        now = func.now()
        (
            self.db.query(User)
            .filter(User.school_id == school_id)
            .update(
                {
                    "plan_effectif": "school",
                    "plan_expiration_at": now + timedelta(days=30),
                },
                synchronize_session="fetch",
            )
        )
        self.db.commit()
        logger.info(f"School members reactivated: school_id={school_id}")

    async def _notifier_utilisateur(self, user_id: str, plan_id: str) -> None:
        """Notifie l'utilisateur de son changement de plan (tache Celery)."""
        try:
            from app.modules.payment.jobs import send_plan_notification
            send_plan_notification.delay(user_id, plan_id)
        except Exception as exc:
            logger.warning(f"Failed to queue notification for user {user_id}: {exc}")
