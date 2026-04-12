from app.modules.payment.routes.payments import router as payments_router
from app.modules.payment.routes.webhook import router as webhook_router
from app.modules.payment.routes.admin import router as payment_admin_router

__all__ = ["payments_router", "webhook_router", "payment_admin_router"]
