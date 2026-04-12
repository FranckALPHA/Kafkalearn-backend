import logging
import os
import uuid
from datetime import datetime

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.ingest.services.base import IngestBaseService

logger = logging.getLogger(__name__)


class FolderScanService(IngestBaseService):
    def lancer_scan_async(self, dossier_path: str, initiated_by) -> str:
        """Create an IngestJob for folder scan and return job_id."""
        from app.modules.ingest.models import IngestJob

        job_id = str(uuid.uuid4())
        job = IngestJob(
            id=job_id,
            initiated_by=initiated_by,
            job_type="folder_scan",
            status="pending",
            dossier_scanne=dossier_path,
        )
        self.db.add(job)
        self.db.commit()
        return job_id

    def scan_and_ingest_sync(self, job_id: str, dossier_path: str):
        """
        Walk directory tree, validate each file, and call ingest_service.process_single_ingest_sync.
        Updates job counters as it processes files.
        """
        from app.modules.ingest.models import IngestJob
        from app.modules.ingest.utils import FileSecurity

        job = self.db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            raise ValueError(f"IngestJob {job_id} not found")

        job.status = "running"
        job.started_at = datetime.utcnow()
        self.db.commit()

        # Count files first
        nb_fichiers = 0
        for root, dirs, files in os.walk(dossier_path):
            # Filter out blacklisted directories
            dirs[:] = [
                d
                for d in dirs
                if not any(d.startswith(prefix) for prefix in (".", "__", "node_modules"))
            ]
            nb_fichiers += len(files)

        job.nb_fichiers_total = nb_fichiers
        self.db.commit()

        # Process each file
        erreurs = []
        for root, dirs, files in os.walk(dossier_path):
            # Filter out blacklisted directories
            dirs[:] = [
                d
                for d in dirs
                if not any(d.startswith(prefix) for prefix in (".", "__", "node_modules"))
            ]

            for filename in files:
                file_path = os.path.join(root, filename)

                try:
                    # Validate path
                    FileSecurity.secure_path(file_path, dossier_path)

                    # Read and validate file
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()

                    FileSecurity.validate_magic_bytes(file_bytes)

                    # Call ingest_service.process_single_ingest_sync
                    from app.modules.ingest.services.ingest_service import IngestService

                    ingest_service = IngestService(
                        db=self.db, redis=self.redis, storage_service=None
                    )
                    ingest_service.process_single_ingest_sync(
                        job_id=job_id,
                        file_path=file_path,
                        nom_original=filename,
                        uploaded_by=job.initiated_by,
                    )

                    job.nb_traites = (job.nb_traites or 0) + 1
                    job.nb_succes = (job.nb_succes or 0) + 1

                except Exception as exc:
                    logger.error(f"Failed to process {file_path}: {exc}")
                    job.nb_traites = (job.nb_traites or 0) + 1
                    job.nb_echecs = (job.nb_echecs or 0) + 1
                    erreurs.append(
                        {
                            "file": file_path,
                            "error": str(exc),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

                # Update job periodically
                job.erreurs_detail = erreurs
                self.db.commit()

        # Finalize job
        if job.nb_echecs and job.nb_succes:
            job.status = "partial"
        elif job.nb_succes:
            job.status = "complete"
        else:
            job.status = "failed"

        job.completed_at = datetime.utcnow()
        self.db.commit()

        return {
            "job_id": job_id,
            "nb_fichiers_total": job.nb_fichiers_total,
            "nb_traites": job.nb_traites,
            "nb_succes": job.nb_succes,
            "nb_echecs": job.nb_echecs,
            "nb_doublons": job.nb_doublons,
        }
