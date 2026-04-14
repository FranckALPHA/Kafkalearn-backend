"""
modules/core/policies.py
========================
Règles d'accès métier (RBAC, Plans).

NOTE : Tous les plans ont les mêmes privilèges (freemium = unlimited).
"""
from app.modules.core.api_errors import api_error

PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited", "school"]


def require_plan(user_plan: str, min_plan: str, lang: str = "fr"):
    """Vérifie que le plan utilisateur est suffisant.

    NOTE : Tous les plans ont les mêmes privilèges — aucune restriction.
    """
    pass
