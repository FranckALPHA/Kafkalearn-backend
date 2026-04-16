"""
routes/admin.py
===============
Admin endpoints for the ingest module.
"""

import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.modules.ingest.schemas.requests import FolderScanRequest
from app.modules.ingest.schemas.responses import IngestReportResponse
from app.modules.ingest.routes.dependencies import (
    get_db,
    get_current_superadmin,
    get_ingest_service,
    get_folder_scan_service,
    get_metadata_queue_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingest - Admin"])


@router.post("/indexer-async", status_code=202)
async def indexer_fichier_async(
    file: UploadFile = File(...),
    force_metadata: str = Form(None),
    current_user: User = Depends(get_current_superadmin),
    ingest_service=Depends(get_ingest_service),
):
    """Upload a file and queue it for async ingestion. Returns job_id and status_url."""
    import json

    parsed_force_metadata = None
    if force_metadata:
        try:
            parsed_force_metadata = json.loads(force_metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="INVALID_FORCE_METADATA_JSON")

    # Save to temp file for Celery worker
    tmp_dir = tempfile.gettempdir()
    tmp_filename = f"{uuid.uuid4()}_{file.filename}"
    tmp_path = os.path.join(tmp_dir, tmp_filename)

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"FILE_SAVE_FAILED: {exc}")

    try:
        result = await ingest_service.ingerer_fichier_async(
            file_bytes=content,
            nom_original=file.filename,
            uploaded_by=current_user.id,
            force_metadata=parsed_force_metadata,
            file_path=tmp_path,
        )
        # Update the task to use file_path instead of file_bytes_b64
        return {
            "job_id": result["job_id"],
            "message": result["message"],
            "status_url": result["status_url"],
        }
    except Exception as exc:
        logger.error(f"Failed to queue ingest job: {exc}")
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"INGEST_QUEUE_FAILED: {exc}")


@router.get("/indexer-report/{job_id}", response_model=IngestReportResponse)
async def get_ingest_report(
    job_id: str,
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Return progress report for an ingest job."""
    from app.modules.ingest.models import IngestJob

    job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="JOB_NOT_FOUND")

    report = job.serialize_report()
    return IngestReportResponse(
        job_id=report["id"],
        status=report["status"],
        nb_fichiers_total=report["nb_fichiers_total"],
        nb_traites=report["nb_traites"],
        nb_succes=report["nb_succes"],
        nb_echecs=report["nb_echecs"],
        nb_doublons=report["nb_doublons"],
        started_at=report["started_at"],
        completed_at=report["completed_at"],
        erreurs_detail=report["erreurs_detail"] or [],
    )


@router.post("/scan-folder", status_code=202)
async def scan_folder(
    body: FolderScanRequest,
    current_user: User = Depends(get_current_superadmin),
    folder_scan_service=Depends(get_folder_scan_service),
    db: Session = Depends(get_db),
):
    """Launch async folder scan. Returns scan_id."""
    import threading
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal

    job_id = folder_scan_service.lancer_scan_async(
        dossier_path=body.chemin_dossier,
        initiated_by=current_user.id,
    )

    dossier_path = body.chemin_dossier

    # Run scan in background thread with its own DB session
    def run_scan():
        from app.modules.ingest.services.folder_scan_service import FolderScanService
        from redis import Redis
        from app.core.database import SessionLocal

        thread_db = SessionLocal()
        thread_redis = Redis.from_url("redis://localhost:6379/0")

        try:
            folder_svc = FolderScanService(db=thread_db, redis=thread_redis)
            folder_svc.scan_and_ingest_sync(
                job_id=job_id,
                dossier_path=dossier_path,
            )
        except Exception as exc:
            logger.error(f"Folder scan failed for job {job_id}: {exc}")
        finally:
            thread_db.close()
            thread_redis.close()

    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()

    return {
        "scan_id": job_id,
        "message": "Folder scan launched",
    }


@router.get("/metadata-queue")
async def get_metadata_queue(
    current_user: User = Depends(get_current_superadmin),
    metadata_queue_service=Depends(get_metadata_queue_service),
):
    """List unresolved metadata queue entries (SuperAdmin only)."""
    entries = metadata_queue_service.obtenir_non_resolus(limit=50)
    return {"entries": entries, "total": len(entries)}


@router.post("/metadata-queue/{queue_id}/resolve")
async def resolve_metadata_queue_entry(
    queue_id: int,
    metadata: dict = None,
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Manually resolve a metadata queue entry."""
    from app.modules.ingest.models import MetadataQueue
    from datetime import datetime

    entry = db.query(MetadataQueue).filter(MetadataQueue.id == queue_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="QUEUE_ENTRY_NOT_FOUND")

    if metadata:
        entry.metadata_tentee = metadata
    entry.is_resolved = True
    entry.resolved_by = current_user.id
    entry.resolved_at = datetime.utcnow()
    db.commit()

    return {"message": "Queue entry resolved", "queue_id": queue_id}
