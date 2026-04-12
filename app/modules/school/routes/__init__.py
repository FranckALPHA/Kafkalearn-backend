from .schools import router as schools_router
from .members import router as members_router
from .billing import router as billing_router
from .admin import router as school_admin_router

__all__ = ["schools_router", "members_router", "billing_router", "school_admin_router"]
