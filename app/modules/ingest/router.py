from fastapi import APIRouter
from app.modules.ingest.routes.admin import router as ingest_admin_router
from app.modules.ingest.routes.worker import router as ingest_worker_router

router = APIRouter()
router.include_router(ingest_admin_router)
router.include_router(ingest_worker_router)
