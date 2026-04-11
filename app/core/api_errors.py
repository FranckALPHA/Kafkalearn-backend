"""
app/core/api_errors.py
======================
Exceptions HTTP standardisées.
"""
from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str = None) -> HTTPException:
    """Construit une HTTPException standardisée."""
    return HTTPException(
        status_code=status_code,
        detail={
            "code": code.upper().replace(".", "_"),
            "message": message or code,
        },
    )
