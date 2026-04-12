from fastapi import APIRouter
from app.modules.wisdom.routes.wisdom import router as wisdom_router
from app.modules.wisdom.routes.admin import router as wisdom_admin_router

router = APIRouter()
router.include_router(wisdom_router)
router.include_router(wisdom_admin_router)
