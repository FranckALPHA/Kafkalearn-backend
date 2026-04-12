from fastapi import APIRouter
from app.modules.school.routes.schools import router as schools_router
from app.modules.school.routes.members import router as members_router
from app.modules.school.routes.billing import router as billing_router
from app.modules.school.routes.admin import router as school_admin_router

router = APIRouter()
router.include_router(schools_router)
router.include_router(members_router)
router.include_router(billing_router)
router.include_router(school_admin_router)
