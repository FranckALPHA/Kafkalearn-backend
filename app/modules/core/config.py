"""
modules/core/config.py
======================
Configuration centralisée avec validation Pydantic.
"""
from pydantic import field_validator
from typing import List, Optional
import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Fallback if pydantic-settings not installed
    class BaseSettings:
        pass
    class SettingsConfigDict:
        pass


class Settings:
    """
    Configuration centrale. En prod, toutes les variables critiques doivent être dans l'environnement.
    """

    # ─── Base de données ─────────────────────────────────────────
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://kafkalearn_user:kafkalearn_password@localhost:15432/kafkalearn_db")
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
    DATABASE_POOL_RECYCLE: int = int(os.getenv("DATABASE_POOL_RECYCLE", "1800"))

    # ─── Redis ───────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:16379/0")
    REDIS_SESSION_TTL: int = int(os.getenv("REDIS_SESSION_TTL", "3600"))
    REDIS_OTP_TTL: int = int(os.getenv("REDIS_OTP_TTL", "600"))

    # ─── Infrastructure Search ───────────────────────────────────
    VESPA_URL: str = os.getenv("VESPA_URL", "http://localhost:18080")
    VESPA_CONFIG_URL: str = os.getenv("VESPA_CONFIG_URL", "http://localhost:19071")

    MEILI_URL: str = os.getenv("MEILI_URL", "http://localhost:17700")
    MEILI_MASTER_KEY: str = os.getenv("MEILI_MASTER_KEY", "")
    MEILI_INDEX: str = os.getenv("MEILI_INDEX", "documents")

    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    # ─── LLM Providers ───────────────────────────────────────────
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openrouter")

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    OPENROUTER_MODEL_FALLBACK: str = os.getenv("OPENROUTER_MODEL_FALLBACK", "google/gemma-3-12b")
    # Compat legacy (non utilises en mode OpenRouter-only)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
    MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")

    # Overrides par tâche
    LLM_PROVIDER_SKILL: Optional[str] = os.getenv("LLM_PROVIDER_SKILL")
    LLM_PROVIDER_SEARCH: Optional[str] = os.getenv("LLM_PROVIDER_SEARCH")

    # ─── Sécurité & JWT ──────────────────────────────────────────
    SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me")
    REFRESH_SECRET_KEY: str = os.getenv("REFRESH_SECRET_KEY", "change-me-refresh")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # ─── Paiement (NotchPay) ─────────────────────────────────────
    NOTCH_SECRET_KEY: str = os.getenv("NOTCH_SECRET_KEY", "")
    NOTCH_PUBLIC_KEY: str = os.getenv("NOTCH_PUBLIC_KEY", "")
    NOTCH_PRIVATE_KEY: str = os.getenv("NOTCH_PRIVATE_KEY", "")
    NOTCH_CALLBACK_URL: str = os.getenv("NOTCH_CALLBACK_URL", "http://localhost:3000/payment/callback")

    # ─── Application & CORS ──────────────────────────────────────
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:9990")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
    API_DEBUG: bool = os.getenv("API_DEBUG", "false").lower() == "true"
    AUTO_CREATE_DB: bool = os.getenv("AUTO_CREATE_DB", "false").lower() in {"1", "true", "yes"}

    DATA_DIR: str = os.getenv("DATA_DIR", "./data")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))

    # ─── Emails (Brevo) ──────────────────────────────────────────
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    MAIL_HOST: str = os.getenv("MAIL_HOST", "smtp.gmail.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "contact@app.cm")

    FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")

    # ─── Google OAuth ────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # ─── Quotas IA ───────────────────────────────────────────────
    QUOTA_IA_FREE: int = int(os.getenv("QUOTA_IA_FREE", "5"))
    QUOTA_IA_PREMIUM: int = int(os.getenv("QUOTA_IA_PREMIUM", "10"))
    QUOTA_IA_PRO: int = int(os.getenv("QUOTA_IA_PRO", "25"))
    QUOTA_IA_UNLIMITED: int = int(os.getenv("QUOTA_IA_UNLIMITED", "200"))

    def get_cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def check_critical_vars(self):
        """Vérifie les variables obligatoires au démarrage."""
        if not self.DATABASE_URL:
            raise SystemExit("ERROR: DATABASE_URL must be set.")


# Singleton global
settings = Settings()
settings.check_critical_vars()
