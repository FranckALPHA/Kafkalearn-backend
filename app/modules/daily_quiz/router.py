from fastapi import APIRouter
from app.modules.daily_quiz.routes.quiz import router as quiz_router
from app.modules.daily_quiz.routes.leaderboard import router as leaderboard_router
from app.modules.daily_quiz.routes.admin import router as daily_quiz_admin_router

router = APIRouter()
router.include_router(quiz_router)
router.include_router(leaderboard_router)
router.include_router(daily_quiz_admin_router)
