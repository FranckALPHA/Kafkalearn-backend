"""
services/storage_service.py
============================
Re-export du StorageService depuis utils pour commodite d'import.
"""
from app.modules.library.utils.storage_service import StorageService

__all__ = ["StorageService"]
