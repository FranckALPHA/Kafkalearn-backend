"""
utils/notchpay_client.py
========================
Client HTTP NotchPay avec retry et signature HMAC.
"""
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import NOTCH_SECRET_KEY, NOTCH_PRIVATE_KEY

logger = logging.getLogger(__name__)


class NotchPayClient:
    """Client pour l'API NotchPay."""

    BASE_URL = "https://api.notchpay.co"

    def __init__(self, api_key: str = None, private_key: str = None):
        self.api_key = api_key or NOTCH_SECRET_KEY
        self._private_key = (private_key or NOTCH_PRIVATE_KEY).encode()
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    )
    async def initialize_payment(
        self,
        amount: int,
        currency: str,
        reference: str,
        email: str,
        callback_url: str,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Initialise un paiement NotchPay."""
        payload = {
            "amount": amount,
            "currency": currency,
            "reference": reference,
            "email": email,
            "callback": callback_url,
            "metadata": metadata or {},
        }
        response = await self.client.post("/payments/initialize", json=payload)
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verifie le statut d'un paiement."""
        response = await self.client.get(f"/payments/{reference}")
        response.raise_for_status()
        return response.json()

    async def initialize_transfer(
        self, amount: int, currency: str, reference: str, beneficiary: str, channel: str
    ) -> Dict[str, Any]:
        """Initialise un transfert sortant."""
        payload = {
            "amount": amount,
            "currency": currency,
            "reference": reference,
            "beneficiary": beneficiary,
            "channel": channel,
        }
        response = await self.client.post("/transfers", json=payload)
        response.raise_for_status()
        return response.json()

    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Verifie la signature HMAC-SHA256 d'un webhook."""
        if not signature or not signature.startswith("sha256="):
            return False
        expected = "sha256=" + hmac.new(self._private_key, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def close(self):
        await self.client.aclose()
