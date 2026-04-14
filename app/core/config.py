"""
app/core/config.py
==================
Compatibilité — re-export depuis modules/core/config.
Conserve les noms de variables legacy pour les imports existants.
"""
import os
from pathlib import Path

from app.modules.core.config import settings

# Backwards compatibility: re-exporter les variables utilisées par l'ancien code
SECRET_KEY = settings.SECRET_KEY
REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
DATABASE_URL = settings.DATABASE_URL
AUTO_CREATE_DB = settings.AUTO_CREATE_DB
REDIS_URL = settings.REDIS_URL
VESPA_URL = settings.VESPA_URL
VESPA_CONFIG_URL = settings.VESPA_CONFIG_URL
MEILI_URL = settings.MEILI_URL
MEILI_MASTER_KEY = settings.MEILI_MASTER_KEY
LLM_PROVIDER = settings.LLM_PROVIDER
LLM_PROVIDER_DEFAULT = settings.LLM_PROVIDER
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
OPENROUTER_API_KEYS = [
    os.getenv("OPENROUTER_API_KEY_1", ""),
    os.getenv("OPENROUTER_API_KEY_2", ""),
    os.getenv("OPENROUTER_API_KEY_3", ""),
    os.getenv("OPENROUTER_API_KEY_4", ""),
]
if not any(OPENROUTER_API_KEYS):
    OPENROUTER_API_KEYS = [settings.OPENROUTER_API_KEY]
OPENROUTER_MODEL = settings.OPENROUTER_MODEL
OPENROUTER_MODEL_FALLBACK = settings.OPENROUTER_MODEL_FALLBACK
OLLAMA_URL = settings.OLLAMA_URL
OLLAMA_MODEL = settings.OLLAMA_MODEL
LLM_MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "2"))
LLM_MIN_INTERVAL_MS = int(os.getenv("LLM_MIN_INTERVAL_MS", "250"))
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
EPREUVES_DIR = DATA_DIR / "epreuves"
USER_DOCS_UPLOAD_DIR = DATA_DIR / "user_docs"
SANDBOX_DIR = DATA_DIR / "sandbox"
SKILLS_DIR = DATA_DIR / "skills"
PROFILE_DIR = DATA_DIR / "profiles"
MAX_UPLOAD_SIZE_MB = settings.MAX_UPLOAD_SIZE_MB
BACKEND_URL = settings.BACKEND_URL
FRONTEND_URL = settings.FRONTEND_URL
CORS_ORIGINS = settings.get_cors_origins()
MAIL_HOST = settings.MAIL_HOST
MAIL_PORT = settings.MAIL_PORT
MAIL_USERNAME = settings.MAIL_USERNAME
MAIL_PASSWORD = settings.MAIL_PASSWORD
MAIL_FROM = settings.MAIL_FROM
BREVO_API_KEY = settings.BREVO_API_KEY
NOTCH_PUBLIC_KEY = settings.NOTCH_PUBLIC_KEY
NOTCH_SECRET_KEY = settings.NOTCH_SECRET_KEY
NOTCH_PRIVATE_KEY = settings.NOTCH_PRIVATE_KEY
NOTCH_WEBHOOK_HASH_KEY = os.getenv("NOTCH_WEBHOOK_HASH_KEY", "")
NOTCH_CALLBACK_URL = settings.NOTCH_CALLBACK_URL
NOTCH_WEBHOOK_URL = os.getenv("NOTCH_WEBHOOK_URL", "")
FIREBASE_SERVICE_ACCOUNT_PATH = settings.FIREBASE_SERVICE_ACCOUNT_PATH
GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
APP_VERSION = settings.APP_VERSION
API_DEBUG = settings.API_DEBUG
SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "superadmin@kafkalearn.cm")
