"""
app/core/database.py
====================
Compatibilité — re-export depuis modules/core/database.
"""
from app.modules.core.database import engine, SessionLocal, Base, get_db, init_db

__all__ = ["engine", "SessionLocal", "Base", "get_db", "init_db"]
