from .sessions import router as sessions_router
from .timetable import router as timetable_router
from .personal_plan import router as personal_plan_router
from .reports import router as reports_router

__all__ = ["sessions_router", "timetable_router", "personal_plan_router", "reports_router"]
