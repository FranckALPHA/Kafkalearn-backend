from fastapi import APIRouter
from app.modules.memory.routes.memory import router as memory_router
from app.modules.memory.routes.admin import router as memory_admin_router
router = APIRouter()
router.include_router(memory_router)
router.include_router(memory_admin_router)
