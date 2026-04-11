"""
app/core/__init__.py
====================
Compatibilité — re-export depuis modules/core.
"""
from app.modules.core.config import settings
from app.modules.core.database import get_db, SessionLocal, Base, engine
from app.modules.core.api_errors import api_error

__all__ = ["settings", "get_db", "SessionLocal", "Base", "engine", "api_error"]
