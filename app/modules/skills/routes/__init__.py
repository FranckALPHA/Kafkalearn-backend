"""
routes/__init__.py
==================
Export des routers du module skills.
"""
from .skills import router as skills_router
from .chat import router as chat_router
from .admin import router as admin_router

__all__ = ["skills_router", "chat_router", "admin_router"]
