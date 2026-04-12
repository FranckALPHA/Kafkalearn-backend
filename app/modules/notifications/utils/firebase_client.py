"""
utils/firebase_client.py
========================
Firebase Cloud Messaging wrapper with graceful fallback when not configured.
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FirebaseClient:
    """Singleton wrapper for FCM. Returns stubbed results if firebase_admin is not installed."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._available = False
        try:
            import firebase_admin  # noqa: F401
            from firebase_admin import credentials, messaging  # noqa: F401

            service_account_path = self._get_service_account_path()
            if service_account_path:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                self._messaging = messaging
                self._available = True
                logger.info("Firebase Admin SDK initialized.")
            else:
                logger.warning("FIREBASE_SERVICE_ACCOUNT_PATH not set.")
        except ImportError:
            logger.warning("firebase_admin not installed. Push notifications disabled.")
        except Exception as exc:
            logger.warning("Failed to initialize Firebase: %s", exc)
        self._initialized = True

    @staticmethod
    def _get_service_account_path() -> Optional[str]:
        import os
        return os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

    def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        priority: str = "normal",
    ) -> Tuple[bool, Optional[str]]:
        """Send a push notification to a single FCM token."""
        if not self._available:
            logger.warning("FCM not available — skipping send_to_token for %s", token[:20])
            return False, "FIREBASE_NOT_CONFIGURED"
        try:
            message = self._messaging.Message(
                notification=self._messaging.Notification(title=title, body=body),
                data=data or {},
                token=token,
                android=self._messaging.AndroidConfig(
                    priority="high" if priority == "high" else "normal",
                ),
                apns=self._messaging.APNSConfig(
                    payload=self._messaging.APNSPayload(
                        aps=self._messaging.Aps(content_available=True),
                    ),
                ),
            )
            response = self._messaging.send(message)
            return True, response
        except Exception as exc:
            error_str = str(exc)
            logger.error("FCM send_to_token error: %s", error_str)
            return False, error_str

    def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Send a push notification to an FCM topic."""
        if not self._available:
            logger.warning("FCM not available — skipping send_to_topic for %s", topic)
            return False, "FIREBASE_NOT_CONFIGURED"
        try:
            message = self._messaging.Message(
                notification=self._messaging.Notification(title=title, body=body),
                data=data or {},
                topic=topic,
            )
            response = self._messaging.send(message)
            return True, response
        except Exception as exc:
            error_str = str(exc)
            logger.error("FCM send_to_topic error: %s", error_str)
            return False, error_str

    @staticmethod
    def is_invalid_token_error(error_code: str) -> bool:
        """Check if an error indicates the token is no longer valid."""
        invalid_markers = [
            "UNREGISTERED",
            "INVALID_ARGUMENT",
            "NOT_FOUND",
            "SenderId mismatch",
            "Invalid registration",
        ]
        return any(marker in (error_code or "").upper() for marker in invalid_markers)
