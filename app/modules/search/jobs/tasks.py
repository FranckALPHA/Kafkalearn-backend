"""
jobs/tasks.py
=============
Tâches Celery pour le module search.
"""
import logging
from datetime import datetime, timedelta

from app.modules.search.jobs.celery_placeholder import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def _get_db():
    return SessionLocal()


@celery_app.task(name="search.tasks.enrich_profile_after_search", queue="default", bind=True, max_retries=3)
def enrich_profile_after_search_task(
    self, user_id: str, requete: str, intention: str, matiere: str, nb_resultats: int
):
    """Enrichit le profil apprenant après une recherche réussie."""
    db = _get_db()
    try:
        from app.modules.users.services.learning_profile_service import LearningProfileService
        LearningProfileService(db).ajouter_recherche(
            user_id=user_id,
            requete=requete,
            intention=intention,
            matiere=matiere,
        )
        db.commit()
    except Exception as e:
        logger.error(f"Erreur enrich_profile user {user_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(name="search.tasks.cleanup_old_search_logs", queue="cron")
def cleanup_old_search_logs(days_to_keep: int = 365):
    """Supprime les search_logs anciens (RGPD)."""
    db = _get_db()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        from app.modules.search.models import SearchLog, SearchChunkReturned

        # Supprimer les chunks d'abord (contrainte FK)
        logs_to_delete = (
            db.query(SearchLog.id)
            .filter(
                SearchLog.created_at < cutoff,
                SearchLog.feedback_rating.is_(None),
            )
            .limit(1000)
            .all()
        )

        if logs_to_delete:
            ids = [row[0] for row in logs_to_delete]
            db.query(SearchChunkReturned).filter(
                SearchChunkReturned.search_log_id.in_(ids)
            ).delete(synchronize_session=False)

            db.query(SearchLog).filter(SearchLog.id.in_(ids)).delete(
                synchronize_session=False
            )
            db.commit()
            logger.info(f"Cleanup: {len(ids)} search_logs supprimés")

        return {"deleted_count": len(logs_to_delete)}
    except Exception as e:
        logger.error(f"Erreur cleanup search_logs: {e}")
        db.rollback()
    finally:
        db.close()
