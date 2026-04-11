"""
routes/__init__.py
==================
Export des routers du module search.
"""
from .search import router as search_router
from .admin import router as search_admin_router

__all__ = ["search_router", "search_admin_router"]
