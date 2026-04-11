"""
router.py
=========
Router principal du module skills.
"""
from fastapi import APIRouter

from app.modules.skills.routes.skills import router as skills_router
from app.modules.skills.routes.chat import router as chat_router
from app.modules.skills.routes.admin import router as admin_router

router = APIRouter()

router.include_router(skills_router)
router.include_router(chat_router)
router.include_router(admin_router)
