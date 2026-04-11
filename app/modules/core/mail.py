"""
modules/core/mail.py
====================
Service Email (placeholder).
"""
import logging

from app.modules.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body_html: str):
    """Envoie un email via Brevo (à implémenter avec brevo-python)."""
    if not settings.BREVO_API_KEY:
        logger.warning("BREVO_API_KEY not set, email not sent")
        return

    # TODO: Implémenter avec brevo-python
    logger.info(f"Email to {to}: {subject}")
