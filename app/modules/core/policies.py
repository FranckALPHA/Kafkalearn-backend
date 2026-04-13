"""
modules/core/policies.py
========================
Règles d'accès métier (RBAC, Plans).
"""
from app.modules.core.api_errors import api_error

PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited", "school"]


def require_plan(user_plan: str, min_plan: str, lang: str = "fr"):
    """Vérifie que le plan utilisateur est suffisant.
    
    NOTE: Disabled for development phase - all users have full access.
    """
    # DEV MODE: Skip plan checks
    return
    try:
        user_level = PLAN_HIERARCHY.index(user_plan)
        min_level = PLAN_HIERARCHY.index(min_plan)
        if user_level < min_level:
            raise api_error(403, "auth.insufficient_permissions", lang, required=min_plan)
    except ValueError:
        raise api_error(500, "server.error", lang)
