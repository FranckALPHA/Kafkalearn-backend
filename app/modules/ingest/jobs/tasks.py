"""
jobs/tasks.py
=============
Celery tasks for the ingest module.
"""
import logging
from datetime import datetime, timedelta

from app.modules.ingest.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    """Create a new DB session for use within Celery tasks."""
    from app.core.database import SessionLocal
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_single_ingest_task(
    self,
    job_id: str,
    file_path: str,
    nom_original: str,
    uploaded_by: str,
    force_metadata: dict = None,
):
    """Process a single file ingestion synchronously (called by Celery worker)."""
    db = _get_db()
    try:
        from app.modules.ingest.services.ingest_service import IngestService

        ingest_service = IngestService(db=db)
        result = ingest_service.process_single_ingest_sync(
            job_id=job_id,
            file_path=file_path,
            nom_original=nom_original,
            uploaded_by=uploaded_by,
            force_metadata=force_metadata,
        )
        return result
    except Exception as exc:
        logger.error(f"Celery task process_single_ingest_task failed for job {job_id}: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def reprocess_metadata_queue_task(self, limit: int = 15, force: bool = False):
    """Reprocess metadata queue entries that failed initial extraction."""
    db = _get_db()
    try:
        import asyncio
        from app.modules.ingest.services.metadata_queue_service import MetadataQueueService

        queue_service = MetadataQueueService(db=db)
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            queue_service.reprocesser_batch(limit=limit, force=force)
        )
        loop.close()
        return result
    except Exception as exc:
        logger.error(f"Celery task reprocess_metadata_queue_task failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task
def audit_pipeline_health_task():
    """Check for stuck jobs, failed workers, and return a health report."""
    db = _get_db()
    try:
        from app.modules.ingest.models import IngestJob, WorkerJob
        from sqlalchemy import func

        now = datetime.utcnow()
        stuck_threshold = now - timedelta(hours=2)

        # Check for stuck ingest jobs
        stuck_ingest_jobs = (
            db.query(IngestJob)
            .filter(
                IngestJob.status.in_(["running", "pending"]),
                IngestJob.created_at < stuck_threshold,
            )
            .all()
        )

        # Check for failed worker jobs
        failed_worker_jobs = (
            db.query(WorkerJob)
            .filter(WorkerJob.status == "failed")
            .all()
        )

        # Check for stuck worker jobs (processing for > 2h)
        stuck_worker_jobs = (
            db.query(WorkerJob)
            .filter(
                WorkerJob.status == "processing",
                WorkerJob.started_at < stuck_threshold,
            )
            .all()
        )

        # Overall stats
        total_ingest_jobs = db.query(func.count(IngestJob.id)).scalar()
        total_worker_jobs = db.query(func.count(WorkerJob.id)).scalar()

        report = {
            "timestamp": now.isoformat(),
            "stuck_ingest_jobs": [
                {"job_id": j.id, "status": j.status, "created_at": j.created_at.isoformat()}
                for j in stuck_ingest_jobs
            ],
            "failed_worker_jobs": [
                {"worker_job_id": j.id, "document_id": j.document_id, "erreur": j.erreur}
                for j in failed_worker_jobs
            ],
            "stuck_worker_jobs": [
                {"worker_job_id": j.id, "document_id": j.document_id, "started_at": j.started_at.isoformat()}
                for j in stuck_worker_jobs
            ],
            "summary": {
                "total_ingest_jobs": total_ingest_jobs,
                "total_worker_jobs": total_worker_jobs,
                "stuck_ingest_count": len(stuck_ingest_jobs),
                "failed_worker_count": len(failed_worker_jobs),
                "stuck_worker_count": len(stuck_worker_jobs),
            },
        }

        logger.info(f"Pipeline health audit: {report['summary']}")
        return report
    except Exception as exc:
        logger.error(f"Celery task audit_pipeline_health_task failed: {exc}")
        raise
    finally:
        db.close()


@celery_app.task
def check_stuck_workers_task():
    """Find WorkerJobs stuck in 'processing' for > 2h and mark them as failed."""
    db = _get_db()
    try:
        from app.modules.ingest.models import WorkerJob

        stuck_threshold = datetime.utcnow() - timedelta(hours=2)

        stuck_jobs = (
            db.query(WorkerJob)
            .filter(
                WorkerJob.status == "processing",
                WorkerJob.started_at < stuck_threshold,
            )
            .all()
        )

        updated_count = 0
        for job in stuck_jobs:
            job.status = "failed"
            job.erreur = "Worker stuck: exceeded 2h processing time"
            job.completed_at = datetime.utcnow()
            updated_count += 1

        if updated_count > 0:
            db.commit()
            logger.info(f"Marked {updated_count} stuck worker jobs as failed")

        return {"checked": len(stuck_jobs), "marked_failed": updated_count}
    except Exception as exc:
        logger.error(f"Celery task check_stuck_workers_task failed: {exc}")
        db.rollback()
        raise
    finally:
        db.close()
