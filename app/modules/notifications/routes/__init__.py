from .user_notifications import router as user_notifications_router
from .admin_notifications import router as admin_notifications_router

__all__ = ["user_notifications_router", "admin_notifications_router"]
