from fastapi import APIRouter
from app.modules.doc_analysis.routes.analysis import router as analysis_router
from app.modules.doc_analysis.routes.admin import router as doc_analysis_admin_router

router = APIRouter()
router.include_router(analysis_router)
router.include_router(doc_analysis_admin_router)
