from fastapi import APIRouter

from app.modules.library.routes.assets import router as assets_router
from app.modules.library.routes.public import router as public_router
from app.modules.library.routes.interactions import router as interactions_router
from app.modules.library.routes.admin import router as library_admin_router

router = APIRouter()
router.include_router(assets_router)
router.include_router(public_router)
router.include_router(interactions_router)
router.include_router(library_admin_router)
