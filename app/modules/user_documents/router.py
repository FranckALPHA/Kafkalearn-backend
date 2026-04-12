from fastapi import APIRouter
from app.modules.user_documents.routes.documents import router as documents_router
from app.modules.user_documents.routes.admin import router as user_documents_admin_router

router = APIRouter()
router.include_router(documents_router)
router.include_router(user_documents_admin_router)
