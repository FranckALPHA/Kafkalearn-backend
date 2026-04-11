from .documents import router as documents_router
from .playlists import router as playlists_router
from .admin import router as admin_router

__all__ = ["documents_router", "playlists_router", "admin_router"]
