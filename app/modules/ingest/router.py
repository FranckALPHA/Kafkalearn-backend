from fastapi import APIRouter
from app.modules.ingest.routes.admin import router as ingest_admin_router

router = APIRouter()
router.include_router(ingest_admin_router)
