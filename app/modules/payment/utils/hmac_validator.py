"""
utils/hmac_validator.py
=======================
Validation HMAC-SHA256 pour les webhooks.
"""
import hmac
import hashlib
from fastapi import HTTPException, status


class HMACValidator:
    @staticmethod
    def verify(body: bytes, signature: str, secret: bytes) -> bool:
        if not signature or not signature.startswith("sha256="):
            return False
        expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def require_valid(body: bytes, signature: str, secret: bytes):
        if not HMACValidator.verify(body, signature, secret):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_SIGNATURE")
