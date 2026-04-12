"""
jobs/tasks.py
=============
Celery tasks for the wisdom module.
"""
import logging

from app.modules.wisdom.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(bind=True, name="wisdom.generate_wisdom_task")
def generate_wisdom_task(self, date_str: str):
    """Genere le wisdom tip pour une date donnee via LLM."""
    import asyncio

    try:
        db_gen = _get_db()
        db = next(db_gen)
    except Exception as exc:
        logger.error("Erreur d'initialisation DB pour generate_wisdom_task: %s", exc)
        return {"status": "error", "message": f"DB init failed: {exc}"}

    try:
        from app.modules.wisdom.services.wisdom_service import WisdomService
        service = WisdomService(db=db)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(service.generer_wisdom_du_jour(date_str))
        finally:
            loop.close()

        if result:
            logger.info("Wisdom tip genere avec succes pour %s", date_str)
            return {"status": "success", "date": date_str, "wisdom_id": result.get("id")}
        else:
            logger.warning("Aucun wisdom tip genere pour %s", date_str)
            return {"status": "skipped", "date": date_str}
    except ImportError as exc:
        logger.error("Module non disponible pour generate_wisdom_task: %s", exc)
        return {"status": "error", "message": f"ImportError: {exc}"}
    except Exception as exc:
        logger.error("Erreur dans generate_wisdom_task pour %s: %s", date_str, exc)
        return {"status": "error", "message": str(exc)}
    finally:
        try:
            db.close()
        except Exception:
            pass


@celery_app.task(bind=True, name="wisdom.send_morning_notification_task")
def send_morning_notification_task(self):
    """Envoie une notification push aux topics d'annonces du matin."""
    try:
        from app.modules.notifications.services import NotificationService
    except ImportError:
        logger.warning("NotificationService non disponible, notification matinale passee.")
        return {"status": "skipped", "message": "NotificationService unavailable"}

    try:
        db_gen = _get_db()
        db = next(db_gen)
    except Exception as exc:
        logger.error("Erreur d'initialisation DB pour send_morning_notification_task: %s", exc)
        return {"status": "error", "message": f"DB init failed: {exc}"}

    try:
        notification_service = NotificationService(db=db)

        # Essayer d'envoyer aux topics d'annonces
        try:
            from app.modules.notifications.utils import FCM_TOPICS
            announcement_topic = FCM_TOPICS.get("announcements", "announcements")
        except (ImportError, AttributeError):
            announcement_topic = "announcements"

        notification_service.send_to_topic(
            topic=announcement_topic,
            title="Sagesse du jour",
            body="Decouvrez votre conseil de sagesse du jour sur KafkaLearn!",
            data={"type": "daily_wisdom", "action": "open_wisdom"},
        )
        logger.info("Notification matinale envoyee au topic %s", announcement_topic)
        return {"status": "success", "topic": announcement_topic}
    except Exception as exc:
        logger.error("Erreur dans send_morning_notification_task: %s", exc)
        return {"status": "error", "message": str(exc)}
    finally:
        try:
            db.close()
        except Exception:
            pass


@celery_app.task(bind=True, name="wisdom.recalculate_ratings_task")
def recalculate_ratings_task(self):
    """Recalcule les ratings moyens pour tous les wisdom tips."""
    import asyncio

    try:
        db_gen = _get_db()
        db = next(db_gen)
    except Exception as exc:
        logger.error("Erreur d'initialisation DB pour recalculate_ratings_task: %s", exc)
        return {"status": "error", "message": f"DB init failed: {exc}"}

    try:
        from app.modules.wisdom.services.wisdom_analytics_service import WisdomAnalyticsService
        service = WisdomAnalyticsService(db=db)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            updated_count = loop.run_until_complete(service.recalculer_tous_ratings())
        finally:
            loop.close()

        logger.info("Recalcul des ratings termine: %d tips mis a jour", updated_count)
        return {"status": "success", "updated_count": updated_count}
    except ImportError as exc:
        logger.error("Module non disponible pour recalculate_ratings_task: %s", exc)
        return {"status": "error", "message": f"ImportError: {exc}"}
    except Exception as exc:
        logger.error("Erreur dans recalculate_ratings_task: %s", exc)
        return {"status": "error", "message": str(exc)}
    finally:
        try:
            db.close()
        except Exception:
            pass
