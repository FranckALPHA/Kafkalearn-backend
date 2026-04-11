"""
app/core/api_errors.py
======================
Compatibilité — re-export depuis modules/core/api_errors.
"""
from app.modules.core.api_errors import api_error

__all__ = ["api_error"]
