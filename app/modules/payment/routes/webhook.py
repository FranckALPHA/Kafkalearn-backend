"""
routes/webhook.py
=================
Endpoint webhook NotchPay — validation HMAC uniquement, pas de JWT.
"""
import logging

from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.modules.payment.routes.dependencies import get_db, get_webhook_service
from app.modules.payment.services import WebhookService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payment/webhook", tags=["payment-webhook"])


@router.post("/", status_code=status.HTTP_200_OK)
async def notchpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    webhook_service: WebhookService = Depends(get_webhook_service),
):
    """
    Reçoit les webhooks NotchPay.
    Valide la signature HMAC puis traite l'événement.
    Retourne toujours 200 pour éviter les retries NotchPay.
    """
    raw_body = await request.body()
    signature = request.headers.get("x-notchpay-signature", "")

    if not signature:
        logger.warning("Webhook reçu sans signature HMAC")
        return {"status": "ignored", "reason": "missing_signature"}

    try:
        result = await webhook_service.traiter_webhook(raw_body, signature)
        db.commit()
        return result
    except ValueError as e:
        logger.error(f"Webhook validation error: {e}")
        # Toujours 200 — NotchPay ne doit pas retryer
        return {"status": "error", "detail": str(e)}
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        # Toujours 200 — on log et on ack
        return {"status": "error", "detail": "internal_error"}
