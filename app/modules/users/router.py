"""
router.py
=========
Router principal du module users - agrège auth, profile, admin, coach, feedback.
"""
from fastapi import APIRouter

from app.modules.users.routes.auth import router as auth_router
from app.modules.users.routes.profile import router as profile_router
from app.modules.users.routes.admin import router as admin_router
from app.modules.users.routes.coach import router as coach_router
from app.modules.users.routes.feedback import router as feedback_router

router = APIRouter()

# Inclure les sous-routers (leurs prefix sont déjà définis)
router.include_router(auth_router)
router.include_router(profile_router)
router.include_router(admin_router)
router.include_router(coach_router)
router.include_router(feedback_router)
