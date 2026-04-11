"""
router.py
=========
Router principal du module search.
"""
from fastapi import APIRouter

from app.modules.search.routes.search import router as search_router
from app.modules.search.routes.admin import router as search_admin_router

router = APIRouter()

router.include_router(search_router)
router.include_router(search_admin_router)
