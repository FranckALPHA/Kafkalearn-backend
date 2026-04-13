"""
modules/core/mail.py
====================
Service Email via Brevo API.
"""
import logging
from typing import Optional

import httpx

from app.modules.core.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


async def send_email(
    to: str,
    subject: str,
    body_html: str,
    sender_name: str = "KafkaLearn",
    reply_to: Optional[str] = None,
) -> Optional[str]:
    """Envoie un email via Brevo API.

    Returns:
        Message-ID de l'email envoye, ou None si l'envoi a echoue.
    """
    if not settings.BREVO_API_KEY:
        logger.warning("BREVO_API_KEY not set, email not sent")
        return None

    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json",
    }

    payload = {
        "sender": {
            "email": settings.MAIL_FROM,
            "name": sender_name,
        },
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": body_html,
    }

    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(BREVO_API_URL, json=payload, headers=headers)
            response.raise_for_status()

            message_id = response.headers.get("X-Message-Id")
            logger.info("Email sent to %s: %s (message-id: %s)", to, subject, message_id)
            return message_id

    except httpx.HTTPStatusError as e:
        logger.error(
            "Brevo API HTTP error for %s: %s - %s",
            to,
            e.response.status_code,
            e.response.text,
        )
        return None
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return None
