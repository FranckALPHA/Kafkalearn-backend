from fastapi import APIRouter

from app.modules.referral.routes.referral import router as referral_router
from app.modules.referral.routes.admin import router as referral_admin_router

router = APIRouter()
router.include_router(referral_router)
router.include_router(referral_admin_router)
