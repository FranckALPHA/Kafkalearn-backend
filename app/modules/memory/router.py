from fastapi import APIRouter
from app.modules.memory.routes.memory import router as memory_router
from app.modules.memory.routes.admin import router as memory_admin_router
from app.modules.memory.routes.cognitive_report import router as cognitive_report_router
from app.modules.memory.routes.graph_extraction import router as graph_extraction_router

router = APIRouter()
router.include_router(memory_router)
router.include_router(memory_admin_router)
router.include_router(cognitive_report_router)
router.include_router(graph_extraction_router)
