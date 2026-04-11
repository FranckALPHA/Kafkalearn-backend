"""
modules/core/api_errors.py
==========================
Factory d'erreurs HTTP standardisées.
"""
from fastapi import HTTPException


def api_error(status_code: int, key: str, lang: str = "fr", **kwargs) -> HTTPException:
    """
    Génère une HTTPException structurée.
    Ex: api_error(404, "document.not_found", "fr", doc_id=123)
    """
    error_code = key.upper().replace(".", "_")
    message = kwargs.get("message", key)

    return HTTPException(
        status_code=status_code,
        detail={
            "code": error_code,
            "message": message,
            "details": {k: v for k, v in kwargs.items() if k != "message"},
        },
    )
