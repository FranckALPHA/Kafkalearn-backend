"""
jobs/tasks.py
=============
Celery tasks for notification operations.
"""
import logging
from datetime import datetime, timedelta

from app.modules.notifications.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    """Create a new DB session for use inside a Celery task."""
    from app.core.database import SessionLocal
    return SessionLocal()


def _get_redis():
    """Get Redis client for use inside a Celery task."""
    try:
        from app.modules.core.redis_client import redis_client
        return redis_client
    except Exception:
        return None


# ─── Push notification task ─────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_push_notification_task(
    self,
    fcm_token: str,
    title: str,
    body: str,
    data: dict = None,
    priority: str = "normal",
    log_id: int = None,
):
    """Send a single push notification via FCM."""
    try:
        from app.modules.notifications.utils.firebase_client import FirebaseClient
        firebase = FirebaseClient()
        success, error = firebase.send_to_token(
            token=fcm_token,
            title=title,
            body=body,
            data=data,
            priority=priority,
        )
        if not success:
            logger.warning("FCM send failed: %s", error)
            raise self.retry(exc=Exception(error))
        return {"success": True, "log_id": log_id}
    except Exception as exc:
        logger.exception("Error in send_push_notification_task")
        raise self.retry(exc=exc)


# ─── Scheduled notification tasks ───────────────────────────────────

@celery_app.task
def send_quiz_morning_task():
    """Send morning quiz notifications to eligible users."""
    try:
        db = _get_db()
        from app.modules.notifications.services.notification_service import NotificationService
        from app.modules.notifications.services.notification_scheduler import NotificationScheduler
        from app.modules.notifications.models import NotificationPreference, Device

        service = NotificationService(db=db)
        scheduler = NotificationScheduler(db=db, redis=_get_redis())

        due = scheduler.get_due_notifications(type_filter="quiz_dispo")
        for item in due:
            user_id = item.get("user_id")
            if user_id:
                service.envoyer_template(
                    user_id=user_id,
                    template_type="quiz_dispo",
                )
                scheduler.mark_sent(f"quiz_dispo:{user_id}")
        logger.info("send_quiz_morning_task completed. Processed %d due notifications.", len(due))
    except Exception:
        logger.exception("Error in send_quiz_morning_task")
    finally:
        db.close()


@celery_app.task
def send_memory_reminders_task():
    """Send memory review reminders that are due."""
    try:
        db = _get_db()
        from app.modules.notifications.services.notification_service import NotificationService
        from app.modules.notifications.services.notification_scheduler import NotificationScheduler

        service = NotificationService(db=db)
        scheduler = NotificationScheduler(db=db, redis=_get_redis())

        due = scheduler.get_due_notifications(type_filter="memory_review")
        for item in due:
            user_id = item.get("user_id")
            nb_sections = item.get("nb_sections", 1)
            if user_id:
                service.envoyer_template(
                    user_id=user_id,
                    template_type="memory_review",
                    params={"nb_sections": nb_sections, "temps_min": nb_sections * 5},
                )
                key = f"memory_review:{user_id}:{item.get('section_id', '')}"
                scheduler.mark_sent(key)
        logger.info("send_memory_reminders_task completed. Processed %d due notifications.", len(due))
    except Exception:
        logger.exception("Error in send_memory_reminders_task")
    finally:
        db.close()


@celery_app.task
def send_streak_danger_task():
    """Send streak danger warnings to users at risk of losing their streak."""
    try:
        db = _get_db()
        from app.modules.notifications.services.notification_service import NotificationService
        from app.modules.users.services.streak_service import StreakService

        service = NotificationService(db=db)
        streak_service = StreakService(db=db)

        # Find users whose streak is in danger (last activity was yesterday or earlier)
        at_risk = streak_service.get_users_at_risk()
        for user_id, nb_jours in at_risk:
            service.envoyer_template(
                user_id=user_id,
                template_type="streak_danger",
                params={"nb_jours": nb_jours},
            )
        logger.info("send_streak_danger_task completed. Warned %d users.", len(at_risk))
    except Exception:
        logger.exception("Error in send_streak_danger_task")
    finally:
        db.close()


@celery_app.task
def cleanup_invalid_tokens_task():
    """Periodically deactivate devices with invalid FCM tokens."""
    try:
        db = _get_db()
        from app.modules.notifications.services.token_cleanup_service import TokenCleanupService

        svc = TokenCleanupService(db=db)
        count = svc.cleanup_invalid_tokens()
        logger.info("cleanup_invalid_tokens_task: deactivated %d devices.", count)
    except Exception:
        logger.exception("Error in cleanup_invalid_tokens_task")
    finally:
        db.close()


@celery_app.task
def cleanup_old_logs_task():
    """Delete notification logs older than 90 days."""
    try:
        db = _get_db()
        from app.modules.notifications.models import NotificationLog

        cutoff = datetime.now() - timedelta(days=90)
        count = (
            db.query(NotificationLog)
            .filter(NotificationLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        logger.info("cleanup_old_logs_task: deleted %d old logs.", count)
    except Exception:
        logger.exception("Error in cleanup_old_logs_task")
    finally:
        db.close()
