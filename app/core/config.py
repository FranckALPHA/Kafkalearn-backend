"""
app/core/config.py
==================
Configuration centralisée du backend KafkaLearn.
"""

import os
from pathlib import Path

# ── Environnement général ────────────────────────────────
API_DEBUG = os.getenv("API_DEBUG", "false").lower() == "true"
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")

# ── Auth & Security ──────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "insecure-default-key-generate-one-!!")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", f"{SECRET_KEY}_refresh")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

# ── Base de données ──────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://kafkalearn_user:kafkalearn_password@localhost:15432/kafkalearn_db"
)
AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "false").lower() in {"1", "true", "yes", "on"}

# ── Redis ────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:16379/0")

# ── Vespa ────────────────────────────────────────────────
VESPA_URL = os.getenv("VESPA_URL", "http://localhost:18080")
VESPA_CONFIG_URL = os.getenv("VESPA_CONFIG_URL", "http://localhost:19071")

# ── MeiliSearch ──────────────────────────────────────────
MEILI_URL = os.getenv("MEILI_URL", "http://localhost:17700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "kafkalearn_master_key")

# ── LLM Providers ────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mistral")
LLM_PROVIDER_DEFAULT = os.getenv("LLM_PROVIDER_DEFAULT", "mistral")

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
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
OPENROUTER_MODEL_FALLBACK = os.getenv("OPENROUTER_MODEL_FALLBACK", "google/gemma-3-12b")

LLM_MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "2"))
LLM_MIN_INTERVAL_MS = int(os.getenv("LLM_MIN_INTERVAL_MS", "250"))

# ── Données & Fichiers ───────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

EPREUVES_DIR = DATA_DIR / "epreuves"
EPREUVES_DIR.mkdir(parents=True, exist_ok=True)

USER_DOCS_UPLOAD_DIR = DATA_DIR / "user_docs"
USER_DOCS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SANDBOX_DIR = DATA_DIR / "sandbox"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

SKILLS_DIR = DATA_DIR / "skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_DIR = DATA_DIR / "profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "20"))

# ── URLs ─────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:9990")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        f"{FRONTEND_URL},http://localhost:3000",
    ).split(",")
    if o.strip()
]

# ── Email ────────────────────────────────────────────────
MAIL_HOST = os.getenv("MAIL_HOST", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", "contact@app.cm")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")

# ── Payment (NotchPay) ───────────────────────────────────
NOTCH_PUBLIC_KEY = os.getenv("NOTCH_PUBLIC_KEY", "")
NOTCH_SECRET_KEY = os.getenv("NOTCH_SECRET_KEY", "")
NOTCH_PRIVATE_KEY = os.getenv("NOTCH_PRIVATE_KEY", "")
NOTCH_WEBHOOK_HASH_KEY = os.getenv("NOTCH_WEBHOOK_HASH_KEY", "")
NOTCH_CALLBACK_URL = os.getenv("NOTCH_CALLBACK_URL", f"{FRONTEND_URL}/payment/callback")
NOTCH_WEBHOOK_URL = os.getenv("NOTCH_WEBHOOK_URL", "")

# ── Firebase (Notifications FCM) ────────────────────────
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")

# ── Google OAuth ─────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
