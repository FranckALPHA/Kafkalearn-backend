"""
routes/__init__.py
==================
Export des routers du module users.
"""
from .auth import router as auth_router
from .profile import router as profile_router
from .admin import router as admin_router

__all__ = ["auth_router", "profile_router", "admin_router"]
