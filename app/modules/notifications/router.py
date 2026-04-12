from fastapi import APIRouter
from app.modules.notifications.routes.user_notifications import router as user_router
from app.modules.notifications.routes.admin_notifications import router as admin_router

router = APIRouter()
router.include_router(user_router)
router.include_router(admin_router)
