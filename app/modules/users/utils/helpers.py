"""
utils/helpers.py
================
Fonctions utilitaires : génération referral_code, validation, sérialisation.
"""
import re
import string
import secrets
from typing import Optional


def generate_referral_code(length: int = 8) -> str:
    """Génère un code de parrainage aléatoire unique (8 chars alphanumériques)."""
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    """Validation basique d'email par regex."""
    return bool(EMAIL_REGEX.match(email))


def normalize_phone(phone: str) -> Optional[str]:
    """
    Normalise un numéro de téléphone.
    Supprime espaces, tirets, parenthèses. Ajoute +237 si numéro camerounais.
    """
    cleaned = re.sub(r"[\s\-\(\)]", "", phone)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 9:
        cleaned = "+237" + cleaned  # Cameroun par défaut
    elif not cleaned.startswith("+"):
        cleaned = "+237" + cleaned
    return cleaned if len(cleaned) >= 8 else None


def serialize_uuid(value) -> Optional[str]:
    """Sérialise un UUID PostgreSQL en string."""
    return str(value) if value else None


def paginate_query(query, page: int = 1, per_page: int = 20):
    """
    Applique la pagination à une requête SQLAlchemy.
    Retourne (items, total, page, per_page, total_pages).
    """
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page
    return items, total, page, per_page, total_pages


def format_duration(minutes: float) -> str:
    """Formate une durée en minutes vers un format lisible."""
    if minutes < 60:
        return f"{int(minutes)}min"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}h"
    days = hours / 24
    return f"{days:.1f}j"
