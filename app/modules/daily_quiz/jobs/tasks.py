import logging
from datetime import date, datetime, timedelta
from sqlalchemy import func

from app.modules.daily_quiz.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    """Create a new DB session for use inside a Celery task."""
    from app.core.database import SessionLocal
    return SessionLocal()


@celery_app.task
def generate_tomorrow_quiz_task():
    """Generate the quiz for tomorrow via DailyQuizGeneratorService."""
    try:
        db = _get_db()
        from app.modules.daily_quiz.services.daily_quiz_generator import DailyQuizGeneratorService

        tomorrow = date.today() + timedelta(days=1)
        generator = DailyQuizGeneratorService(db=db)
        result = generator.generer_quiz_du_jour(date_cible=tomorrow, force=False)

        # Handle async result if needed
        if hasattr(result, "__await__"):
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(result)

        logger.info("generate_tomorrow_quiz_task completed for %s", tomorrow)
    except Exception:
        logger.exception("Error in generate_tomorrow_quiz_task")
    finally:
        db.close()


@celery_app.task
def notify_quiz_available_task():
    """Send push notification to quiz_dispo_fr and quiz_dispo_en topics."""
    try:
        db = _get_db()
        from app.modules.notifications.services.notification_service import NotificationService

        service = NotificationService(db=db)
        service.send_to_topic(
            topic="quiz_dispo_fr",
            title="Quiz du jour disponible!",
            body="Testez vos connaissances avec le quiz du jour.",
            type_notif="quiz_dispo",
        )
        service.send_to_topic(
            topic="quiz_dispo_en",
            title="Daily Quiz Available!",
            body="Test your knowledge with today's quiz.",
            type_notif="quiz_dispo",
        )

        # Notify users with milestone streaks
        try:
            from app.modules.daily_quiz.services.quiz_streak_service import QuizStreakService
            from app.modules.daily_quiz.models import DailyQuizAttempt

            streak_svc = QuizStreakService(db, None)
            # Find users whose streak just hit a milestone
            today_start = datetime.combine(date.today(), datetime.min.time())
            recent_attempts = (
                db.query(DailyQuizAttempt.user_id)
                .filter(DailyQuizAttempt.created_at >= today_start)
                .distinct()
                .all()
            )
            for (user_id,) in recent_attempts:
                streak_info = streak_svc.get_streak_info(user_id)
                current = streak_info.get("current_streak", 0)
                if current in (3, 7, 14, 30, 100):
                    service.send_to_user(
                        user_id=user_id,
                        title=f"{current} jours de suite!",
                        body=f"Continuez comme ca! Vous avez complete {current} jours de quiz consecutifs.",
                        type_notif="quiz_dispo",
                    )
        except Exception:
            logger.exception("Error sending streak milestone notifications")

        logger.info("notify_quiz_available_task completed")
    except Exception:
        logger.exception("Error in notify_quiz_available_task")
    finally:
        db.close()


@celery_app.task
def calculate_monthly_ranks_task():
    """Calculate and set leaderboard ranks for the current month."""
    try:
        db = _get_db()
        from app.modules.daily_quiz.services.leaderboard_service import LeaderboardService

        month_year = datetime.now().strftime("%Y-%m")
        leaderboard_svc = LeaderboardService(db=db)
        count = leaderboard_svc.calculer_rangs(month_year=month_year)

        logger.info("calculate_monthly_ranks_task completed for %s. Processed %d entries.", month_year, count)
    except Exception:
        logger.exception("Error in calculate_monthly_ranks_task")
    finally:
        db.close()
