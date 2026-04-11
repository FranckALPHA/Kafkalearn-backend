"""
app/modules/epreuves/jobs/tasks.py
===================================
Tâches Celery asynchrones pour le module epreuves.
"""
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import Integer

from app.modules.epreuves.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    from app.core.database import SessionLocal
    return SessionLocal()


# ─── Ingestion ───────────────────────────────────────────────────────

@celery_app.task(name="epreuves.tasks.run_ingestion", queue="heavy", bind=True, max_retries=3)
def run_ingestion(self, doc_id: int):
    """Lance le pipeline d'ingestion complet pour un document."""
    db = _get_db()
    try:
        from app.modules.epreuves.services.document_ingest_service import DocumentIngestService
        service = DocumentIngestService(db=db)
        result = service.run_full_ingestion(doc_id)
        logger.info(f"Ingestion completed for doc {doc_id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Ingestion failed for doc {doc_id}: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


# ─── Stats & tracking ────────────────────────────────────────────────

@celery_app.task(name="epreuves.tasks.log_document_view", queue="default")
def log_document_view_task(document_id: int, user_id: str = None, source: str = "view"):
    """Log une consultation de document."""
    db = _get_db()
    try:
        from app.modules.epreuves.models import DocumentView
        from app.modules.epreuves.models import Document

        view = DocumentView(
            document_id=document_id,
            user_id=user_id,
            source=source,
        )
        db.add(view)

        # Incrément nb_vues atomique
        db.query(Document).filter(Document.id == document_id).update(
            {Document.nb_vues: Document.nb_vues + 1}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Log view failed for doc {document_id}: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="epreuves.tasks.log_download", queue="default")
def log_download_task(document_id: int, user_id: str):
    """Log un téléchargement de document."""
    db = _get_db()
    try:
        from app.modules.epreuves.models import DocumentView
        from app.modules.epreuves.models import Document

        view = DocumentView(
            document_id=document_id,
            user_id=user_id,
            source="download",
        )
        db.add(view)

        db.query(Document).filter(Document.id == document_id).update(
            {Document.nb_telechargements: Document.nb_telechargements + 1}
        )
        db.commit()
    except Exception as e:
        logger.error(f"Log download failed for doc {document_id}: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="epreuves.tasks.increment_document_stat", queue="default")
def increment_document_stat_task(document_id: int, stat_field: str, value: int = 1):
    """Incrémente une statistique de document."""
    db = _get_db()
    try:
        from app.modules.epreuves.models import Document
        from sqlalchemy import update

        db.execute(
            update(Document).where(Document.id == document_id).values(
                {stat_field: getattr(Document, stat_field) + value}
            )
        )
        db.commit()
    except Exception as e:
        logger.error(f"Stat increment failed for doc {document_id}: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="epreuves.tasks.update_document_stats", queue="default", bind=True, max_retries=2)
def update_document_stats_task(self, doc_id: int, stat_field: str, value: int):
    """Met à jour les statistiques d'un document."""
    db = _get_db()
    try:
        from app.modules.epreuves.services.document_stats_service import DocumentStatsService
        service = DocumentStatsService(db=db)
        service.get_stats_document(doc_id)
    except Exception as e:
        logger.error(f"Stats update failed for doc {doc_id}: {e}")
    finally:
        db.close()


# ─── Cron tasks ──────────────────────────────────────────────────────

@celery_app.task(name="epreuves.tasks.recalculate_trending", queue="cron")
def recalculate_trending_task(periode_jours: int = 7):
    """Recalcule les scores trending et met à jour le cache Redis."""
    db = _get_db()
    try:
        from app.modules.epreuves.models import DocumentView
        from sqlalchemy import func
        from app.core.config import REDIS_URL
        from redis import Redis

        cutoff = datetime.utcnow() - timedelta(days=periode_jours)

        trending = (
            db.query(
                DocumentView.document_id,
                func.count().label("nb_vues"),
                func.sum((DocumentView.source == "download").cast(Integer)).label("nb_telechargements"),
            )
            .filter(DocumentView.created_at >= cutoff)
            .group_by(DocumentView.document_id)
            .all()
        )

        redis = Redis.from_url(REDIS_URL, decode_responses=True, db=3)
        cache_key = f"epreuves:trending:{periode_jours}j"

        results = []
        for doc_id, vues, telechargements in trending:
            score = (vues or 0) * 1 + (telechargements or 0) * 3
            results.append({"document_id": doc_id, "trending_score": score})

        results.sort(key=lambda x: x["trending_score"], reverse=True)
        redis.setex(cache_key, 3600, json.dumps(results[:50]))

        logger.info(f"Trending recalculated: {len(results)} documents")
        return {"count": len(results)}

    except Exception as e:
        logger.error(f"Erreur recalcul trending: {e}")
        raise
    finally:
        db.close()


@celery_app.task(name="epreuves.tasks.cleanup_old_views", queue="cron")
def cleanup_old_views_task(days_to_keep: int = 90):
    """Supprime les document_views anciennes."""
    db = _get_db()
    try:
        from app.modules.epreuves.models import DocumentView

        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        batch_size = 5000
        deleted = 0

        while True:
            ids = [
                row[0]
                for row in db.query(DocumentView.id)
                .filter(DocumentView.created_at < cutoff)
                .limit(batch_size)
                .all()
            ]
            if not ids:
                break
            db.query(DocumentView).filter(DocumentView.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
            deleted += len(ids)

        logger.info(f"Cleanup views: {deleted} supprimées")
        return {"deleted_count": deleted}

    except Exception as e:
        logger.error(f"Erreur cleanup views: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="epreuves.tasks.alert_missing_files", queue="cron")
def alert_missing_files_task():
    """Vérifie l'existence physique des fichiers des documents validés."""
    db = _get_db()
    try:
        from app.modules.epreuves.models import Document
        from app.modules.epreuves.utils.storage import StorageService

        storage = StorageService()
        missing = []

        docs = (
            db.query(Document)
            .filter(Document.is_validated == True, Document.chemin_final != None)
            .all()
        )

        for doc in docs:
            if not storage.file_exists(doc.chemin_final):
                missing.append({"document_id": doc.id, "nom_original": doc.nom_original})
                logger.error(f"Missing file: doc {doc.id} - {doc.nom_original}")

        if missing:
            logger.warning(f"ALERT: {len(missing)} documents have missing files")

        return {"checked": len(docs), "missing": len(missing)}

    except Exception as e:
        logger.error(f"Erreur check fichiers: {e}")
        raise
    finally:
        db.close()
