from fastapi import APIRouter
from app.modules.payment.routes.payments import router as payments_router
from app.modules.payment.routes.webhook import router as webhook_router
from app.modules.payment.routes.admin import router as payment_admin_router

router = APIRouter()
router.include_router(payments_router)
router.include_router(webhook_router)
router.include_router(payment_admin_router)
