"""
services/qr_code_service.py
============================
Generates QR codes for referral links with Redis caching.
"""
import asyncio
import logging
import io

logger = logging.getLogger(__name__)


class QRCodeService:
    """Generate QR codes for referral links with optional Redis caching."""

    def __init__(self, cache_redis=None, cache_ttl: int = 86400):
        self.cache = cache_redis
        self.cache_ttl = cache_ttl

    def generer_qr_code(self, referral_link: str, size: int = 300) -> bytes:
        """Generate a QR code image as PNG bytes.

        Args:
            referral_link: The URL to encode in the QR code.
            size: Size of the QR code image in pixels.

        Returns:
            PNG image bytes, or empty bytes if qrcode library not available.
        """
        try:
            import qrcode
            from PIL import Image

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(referral_link)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img = img.resize((size, size), Image.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return buffer.getvalue()

        except ImportError:
            logger.warning(
                "qrcode or PIL not installed. Install with: pip install qrcode[pil]"
            )
            return b""
        except Exception as e:
            logger.error("Error generating QR code: %s", e)
            return b""

    async def generer_avec_cache(self, user_id: str, referral_link: str) -> bytes:
        """Generate a QR code with Redis caching.

        Args:
            user_id: User identifier for cache key.
            referral_link: The URL to encode.

        Returns:
            PNG image bytes.
        """
        if self.cache:
            cache_key = f"qr_code:{user_id}"
            try:
                cached = self.cache.get(cache_key)
                if cached:
                    # Redis stores as string, need to convert back
                    import base64
                    return base64.b64decode(cached)
            except Exception:
                pass

        # Generate fresh QR code
        qr_bytes = self.generer_qr_code(referral_link)

        # Cache it
        if self.cache and qr_bytes:
            try:
                import base64
                encoded = base64.b64encode(qr_bytes).decode("utf-8")
                self.cache.setex(cache_key, self.cache_ttl, encoded)
            except Exception as e:
                logger.warning("Failed to cache QR code: %s", e)

        return qr_bytes
