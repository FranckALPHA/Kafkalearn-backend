"""
jobs/tasks.py
=============
Celery tasks for the memory module.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.modules.memory.jobs.celery_app import celery_app
from app.modules.memory.services.memory_stats_service import MemoryStatsService
from app.modules.memory.services.memory_generator_service import MemoryGeneratorService
from app.modules.memory.models import MemorySection, UserSectionProgress

logger = logging.getLogger(__name__)


def _get_db() -> Session:
    """Create a new DB session for use inside Celery tasks."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    return db


# -------------------------------------------------------------------
# Task: Generate memory items for a section
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_memory_items_task(self, document_id: int, section_title: str, texte_section: str, langue: str = "fr"):
    """Generate memory items for a document section via MemoryGeneratorService."""
    db = _get_db()
    try:
        from app.modules.memory.services.memory_generator_service import MemoryGeneratorService
        service = MemoryGeneratorService(db=db)
        import asyncio
        result = asyncio.run(service.generer_pack_section(
            document_id=document_id,
            section_title=section_title,
            texte_section=texte_section,
            langue=langue,
        ))
        logger.info("Generated %d items for section '%s'", result.get("nb_items_generes", 0), section_title)
        return result
    except Exception as exc:
        logger.error("Failed to generate memory items: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Send review reminder to a single user
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def send_review_reminder_task(self, user_id: str, sections_due: list):
    """Send a review reminder notification to a user for due sections."""
    db = _get_db()
    try:
        try:
            from app.modules.notifications.services.notification_service import NotificationService
        except ImportError:
            logger.warning("NotificationService not available; skipping reminder for user %s", user_id)
            return {"status": "skipped", "reason": "NotificationService not available"}

        service = NotificationService(db=db)
        message = f"You have {len(sections_due)} section(s) to review today."
        notification = service.send_notification(
            user_id=user_id,
            notification_type="review_reminder",
            title="Time to Review!",
            message=message,
            data={"sections_due": sections_due},
        )
        logger.info("Sent review reminder to user %s", user_id)
        return {"status": "sent", "user_id": user_id, "notification_id": notification.id if notification else None}
    except Exception as exc:
        logger.error("Failed to send review reminder to user %s: %s", user_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Send daily review reminders to all users with due sections
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def send_daily_review_reminders_task(self):
    """Find users with due sections and send daily review reminders."""
    db = _get_db()
    try:
        now = datetime.now(timezone.utc)
        # Check anti-duplicate flag in Redis
        try:
            from redis import Redis
            from app.core.config import REDIS_URL
            redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
            today_key = f"memory:daily_reminder_sent:{now.strftime('%Y-%m-%d')}"
            if redis_client.exists(today_key):
                logger.info("Daily review reminders already sent today")
                return {"status": "skipped", "reason": "already_sent_today"}
        except Exception:
            logger.warning("Redis not available; proceeding without anti-duplicate check")
            redis_client = None

        # Find users with due sections
        rows = (
            db.query(UserSectionProgress.user_id)
            .filter(
                UserSectionProgress.is_completed.is_(True),
                UserSectionProgress.next_review_at.isnot(None),
                UserSectionProgress.next_review_at <= now,
            )
            .distinct()
            .all()
        )

        user_ids = [row[0] for row in rows]
        if not user_ids:
            logger.info("No users with due sections for daily reminder")
            return {"status": "no_due_sections"}

        sent_count = 0
        for user_id in user_ids:
            sections_due = (
                db.query(MemorySection)
                .join(UserSectionProgress, UserSectionProgress.section_id == MemorySection.id)
                .filter(
                    UserSectionProgress.user_id == user_id,
                    UserSectionProgress.next_review_at <= now,
                )
                .all()
            )
            send_review_reminder_task.delay(
                user_id=user_id,
                sections_due=[{"section_id": s.id, "title": s.section_title} for s in sections_due],
            )
            sent_count += 1

        # Set anti-duplicate flag (24h TTL)
        if redis_client:
            redis_client.setex(today_key, 86400, "1")

        logger.info("Queued daily review reminders for %d users", sent_count)
        return {"status": "queued", "users_count": sent_count}
    except Exception as exc:
        logger.error("Failed to send daily review reminders: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Regenerate weekly packs older than 7 days
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def regenerate_weekly_packs_task(self):
    """Regenerate memory packs older than 7 days."""
    db = _get_db()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        stale_sections = (
            db.query(MemorySection)
            .filter(
                MemorySection.generation_status == "complete",
                MemorySection.generated_at < cutoff,
            )
            .all()
        )

        if not stale_sections:
            logger.info("No stale packs to regenerate")
            return {"status": "no_stale_packs"}

        regenerated = 0
        for section in stale_sections:
            try:
                service = MemoryGeneratorService(db=db)
                import asyncio
                result = asyncio.run(service.regenerer_section(section_id=section.id, force=True))
                if result.get("nb_items_generes", 0) > 0:
                    regenerated += 1
                logger.info("Regenerated section %d: %d items", section.id, result.get("nb_items_generes", 0))
            except Exception as exc:
                logger.error("Failed to regenerate section %d: %s", section.id, exc)

        logger.info("Regenerated %d/%d stale packs", regenerated, len(stale_sections))
        return {"status": "done", "regenerated": regenerated, "total": len(stale_sections)}
    except Exception as exc:
        logger.error("Failed to regenerate weekly packs: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
    finally:
        db.close()


# -------------------------------------------------------------------
# Task: Update item difficulty from recent attempts
# -------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def update_item_difficulty_task(self):
    """Recalculate item difficulty from recent attempts across all sections."""
    db = _get_db()
    try:
        service = MemoryStatsService(db=db)

        # Get all sections with attempts
        sections = (
            db.query(MemorySection.id)
            .join(UserSectionProgress, UserSectionProgress.section_id == MemorySection.id)
            .distinct()
            .all()
        )

        updated = 0
        for (section_id,) in sections:
            try:
                import asyncio
                asyncio.run(service.mettre_a_jour_difficulte_section(section_id))
                updated += 1
            except Exception as exc:
                logger.error("Failed to update difficulty for section %d: %s", section_id, exc)

        logger.info("Updated difficulty for %d sections", updated)
        return {"status": "done", "sections_updated": updated}
    except Exception as exc:
        logger.error("Failed to update item difficulty: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()
