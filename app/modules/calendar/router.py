from fastapi import APIRouter
from app.modules.calendar.routes.sessions import router as sessions_router
from app.modules.calendar.routes.timetable import router as timetable_router
from app.modules.calendar.routes.personal_plan import router as personal_plan_router
from app.modules.calendar.routes.reports import router as reports_router

router = APIRouter()
router.include_router(sessions_router)
router.include_router(timetable_router)
router.include_router(personal_plan_router)
router.include_router(reports_router)
