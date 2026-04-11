"""
router.py
=========
Router principal du module epreuves.
"""
from fastapi import APIRouter

from app.modules.epreuves.routes.documents import router as documents_router
from app.modules.epreuves.routes.playlists import router as playlists_router
from app.modules.epreuves.routes.admin import router as admin_router

router = APIRouter()

router.include_router(documents_router)
router.include_router(playlists_router)
router.include_router(admin_router)
