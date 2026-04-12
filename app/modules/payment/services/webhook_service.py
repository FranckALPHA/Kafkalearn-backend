"""
services/webhook_service.py
============================
Traitement des webhooks NotchPay avec validation HMAC.
"""
import json
import logging
from typing import Dict, Any

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.payment.models import Transaction
from app.modules.payment.utils.hmac_validator import HMACValidator
from app.modules.payment.services.base import PaymentBaseService
from app.core.config import NOTCH_PRIVATE_KEY

logger = logging.getLogger(__name__)


class WebhookService(PaymentBaseService):
    """Service de traitement des webhooks NotchPay."""

    def __init__(self, db: Session, redis: Redis = None, notchpay_private_key: str = None):
        super().__init__(db, redis)
        self._private_key = (notchpay_private_key or NOTCH_PRIVATE_KEY).encode()

    async def traiter_webhook(self, body: bytes, signature: str) -> Dict[str, Any]:
        """Valide et route un webhook NotchPay."""
        HMACValidator.require_valid(body, signature, self._private_key)

        data = json.loads(body)
        event_type = data.get("event", "").lower()
        reference = data.get("reference", data.get("tx", {}).get("reference"))

        if not reference:
            raise ValueError("Webhook missing reference field")

        logger.info(f"Processing webhook: event={event_type}, reference={reference}")

        if event_type in ("payment.completed", "payment.success", "payment.completed"):
            return await self._handle_payment_complete(reference, data)
        elif event_type in ("transfer.completed", "transfer.success"):
            return await self._handle_transfer(reference, data, event_type)
        else:
            logger.warning(f"Unhandled webhook event: {event_type}")
            return {"status": "ignored", "event": event_type}

    async def _handle_payment_complete(
        self, reference: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Traite un webhook de paiement reussi avec idempotence."""
        transaction = (
            self.db.query(Transaction)
            .with_for_update()
            .filter(Transaction.gateway_ref == reference)
            .first()
        )
        if not transaction:
            raise ValueError(f"Transaction not found for reference: {reference}")

        # Idempotence check
        if transaction.status == "complete":
            logger.info(f"Transaction already complete: {reference}")
            return {"status": "idempotent", "transaction_id": transaction.id}

        # Amount mismatch check
        received_amount = data.get("amount") or data.get("tx", {}).get("amount")
        if received_amount and int(received_amount) != transaction.amount:
            logger.error(
                f"Amount mismatch: expected={transaction.amount}, received={received_amount}"
            )
            transaction.status = "failed"
            transaction.raw_data = data
            self.db.commit()
            return {"status": "amount_mismatch"}

        transaction.status = "complete"
        transaction.raw_data = data
        self.db.commit()

        # Queue Celery task for subscription validation
        try:
            from app.modules.payment.jobs import validate_subscription_task
            validate_subscription_task.delay(transaction.id)
        except Exception as exc:
            logger.warning(f"Failed to queue validation task: {exc}")

        return {
            "status": "processed",
            "transaction_id": transaction.id,
            "user_id": str(transaction.user_id),
            "plan_id": transaction.plan_id,
        }

    async def _handle_transfer(
        self, reference: str, data: Dict[str, Any], event_type: str
    ) -> Dict[str, Any]:
        """Traite un webhook de transfert."""
        transaction = (
            self.db.query(Transaction)
            .with_for_update()
            .filter(Transaction.gateway_ref == reference)
            .first()
        )
        if not transaction:
            raise ValueError(f"Transfer transaction not found: {reference}")

        if transaction.status == "complete":
            return {"status": "idempotent", "transaction_id": transaction.id}

        if "failed" in event_type or "cancel" in event_type:
            transaction.status = "failed"
        else:
            transaction.status = "complete"

        transaction.raw_data = data
        self.db.commit()

        return {
            "status": "processed",
            "transaction_id": transaction.id,
            "type": "transfer",
        }
