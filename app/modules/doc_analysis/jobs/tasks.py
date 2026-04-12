"""
app/modules/doc_analysis/jobs/tasks.py
=======================================
Tâches Celery asynchrones pour le module doc_analysis.
"""
import logging

from app.modules.doc_analysis.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    from app.core.database import SessionLocal
    return SessionLocal()


# ─── Access counter ──────────────────────────────────────────────

@celery_app.task(name="doc_analysis.tasks.increment_analysis_access", queue="default")
def increment_analysis_access_task(analysis_id: int):
    """Increments nb_acces on a DocumentAnalysis record."""
    db = _get_db()
    try:
        from app.modules.doc_analysis.models import DocumentAnalysis
        analysis = (
            db.query(DocumentAnalysis)
            .filter(DocumentAnalysis.id == analysis_id)
            .first()
        )
        if analysis:
            analysis.nb_acces += 1
            db.commit()
            logger.info(f"Incremented access count for analysis {analysis_id}")
        else:
            logger.warning(f"Analysis {analysis_id} not found for access increment")
    except Exception as exc:
        logger.error(f"Failed to increment access count: {exc}", exc_info=True)
    finally:
        db.close()


# ─── Cache pre-heating ───────────────────────────────────────────

@celery_app.task(name="doc_analysis.tasks.analyze_missing_documents", queue="heavy", bind=True, max_retries=2)
def analyze_missing_documents_task(self, limit: int = 50, langue: str = "fr"):
    """Pre-heats cache by analyzing documents without analyses."""
    db = _get_db()
    try:
        from app.modules.doc_analysis.services.document_analysis_service import DocumentAnalysisService
        from app.modules.doc_analysis.models import DocumentAnalysis
        from app.modules.epreuves.models.document import Document
        import asyncio

        analyzed_ids = (
            db.query(DocumentAnalysis.document_id)
            .filter(DocumentAnalysis.langue == langue)
            .distinct()
            .all()
        )
        analyzed_id_set = {row[0] for row in analyzed_ids}

        documents = (
            db.query(Document)
            .filter(Document.id.notin_(analyzed_id_set) if analyzed_id_set else True)
            .limit(limit)
            .all()
        )

        if not documents:
            logger.info("No missing documents to analyze")
            return {"processed": 0}

        service = DocumentAnalysisService(db=db)
        processed = 0

        for doc in documents:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    service.analyser_ou_retourner_cache(
                        document_id=doc.id,
                        langue=langue,
                        user_plan="freemium",
                    )
                )
                loop.close()
                processed += 1
            except Exception as exc:
                logger.warning(f"Failed to analyze doc {doc.id}: {exc}")

        logger.info(f"Pre-heated {processed}/{len(documents)} analyses")
        return {"processed": processed, "total": len(documents)}

    except Exception as exc:
        logger.error(f"analyze_missing_documents failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()


# ─── Cache coherence ─────────────────────────────────────────────

@celery_app.task(name="doc_analysis.tasks.verify_cache_coherence", queue="default")
def verify_cache_coherence_task():
    """Checks hash coherence and invalidates obsolete analyses."""
    db = _get_db()
    try:
        from app.modules.doc_analysis.services.analysis_cache_service import AnalysisCacheService
        from app.modules.epreuves.models.document import Document

        documents = db.query(Document).all()
        total_checked = 0
        total_invalidated = 0

        for doc in documents:
            try:
                result = db.run_sync(
                    lambda s: AnalysisCacheService(db=s).verifier_coherence_hash(doc.id)
                )
                total_checked += 1
                if not result["coherent"]:
                    count = db.run_sync(
                        lambda s: AnalysisCacheService(db=s).invalider_analyses_document(doc.id)
                    )
                    total_invalidated += count
            except ValueError:
                pass
            except Exception as exc:
                logger.warning(f"Coherence check failed for doc {doc.id}: {exc}")

        logger.info(
            f"Cache coherence: checked={total_checked}, invalidated={total_invalidated}"
        )
        return {"checked": total_checked, "invalidated": total_invalidated}

    except Exception as exc:
        logger.error(f"verify_cache_coherence failed: {exc}", exc_info=True)
    finally:
        db.close()


# ─── Flush access counters ───────────────────────────────────────

@celery_app.task(name="doc_analysis.tasks.flush_access_counters", queue="default")
def flush_access_counters_task():
    """Flushes Redis access counters to DB."""
    db = _get_db()
    try:
        from redis import Redis
        from app.core.config import REDIS_URL
        from app.modules.doc_analysis.models import DocumentAnalysis

        redis = Redis.from_url(REDIS_URL, decode_responses=True, db=10)
        pattern = "doc_analysis:access:*"
        keys = redis.keys(pattern)

        flushed = 0
        for key in keys:
            try:
                analysis_id = int(key.split(":")[-1])
                count = int(redis.get(key) or 0)
                if count > 0:
                    db.query(DocumentAnalysis).filter(
                        DocumentAnalysis.id == analysis_id
                    ).update(
                        {DocumentAnalysis.nb_acces: DocumentAnalysis.nb_acces + count},
                        synchronize_session=False,
                    )
                    redis.delete(key)
                    flushed += 1
            except (ValueError, TypeError) as exc:
                logger.warning(f"Failed to parse key {key}: {exc}")

        if flushed > 0:
            db.commit()

        logger.info(f"Flushed {flushed} access counters to DB")
        return {"flushed": flushed}

    except Exception as exc:
        logger.error(f"flush_access_counters failed: {exc}", exc_info=True)
    finally:
        db.close()
