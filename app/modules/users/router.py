"""
router.py
=========
Router principal du module users - agrège auth, profile, admin.
"""
from fastapi import APIRouter

from app.modules.users.routes.auth import router as auth_router
from app.modules.users.routes.profile import router as profile_router
from app.modules.users.routes.admin import router as admin_router

router = APIRouter()

# Inclure les sous-routers (leurs prefix sont déjà définis)
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(admin_router)
