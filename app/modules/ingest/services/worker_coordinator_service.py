import logging
from datetime import datetime

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.ingest.services.base import IngestBaseService

logger = logging.getLogger(__name__)


class WorkerCoordinatorService(IngestBaseService):
    def lister_documents_a_embedder(self, limit: int = 10) -> list:
        """Return documents not yet embedded with extracted text."""
        from app.modules.ingest.models import WorkerJob

        # Find pending embed worker jobs with their documents
        jobs = (
            self.db.query(WorkerJob)
            .filter(
                WorkerJob.status == "pending",
                WorkerJob.job_type.in_(["embed", "both"]),
            )
            .join(
                WorkerJob.document,
            )
            .filter(
                WorkerJob.document.texte_extrait.isnot(None),
                WorkerJob.document.is_validated == True,  # noqa: E712
            )
            .limit(limit)
            .all()
        )

        result = []
        for job in jobs:
            doc = job.document
            result.append(
                {
                    "worker_job_id": job.id,
                    "document_id": doc.id,
                    "nom_original": doc.nom_original,
                    "matiere": doc.matiere,
                    "niveau": doc.niveau,
                    "texte_extrait": doc.texte_extrait,
                    "chemin_final": doc.chemin_final,
                }
            )

        return result

    def sauvegarder_resultats_worker(
        self,
        doc_id: int,
        worker_id: str,
        succes: bool,
        nb_chunks: int = 0,
        erreur: str = None,
    ):
        """Update WorkerJob status and Document is_embedded flag."""
        from app.modules.ingest.models import WorkerJob
        from app.modules.epreuves.models import Document

        # Find the worker job for this document
        worker_job = (
            self.db.query(WorkerJob)
            .filter(
                WorkerJob.document_id == doc_id,
                WorkerJob.status.in_(["pending", "processing", "downloaded"]),
            )
            .first()
        )

        if not worker_job:
            logger.warning(f"No pending WorkerJob found for document {doc_id}")
            # Create one if it doesn't exist
            worker_job = WorkerJob(
                document_id=doc_id,
                job_type="embed",
                status="complete" if succes else "failed",
                worker_id=worker_id,
                nb_chunks_generes=nb_chunks if succes else 0,
                erreur=erreur if not succes else None,
                completed_at=datetime.utcnow(),
            )
            self.db.add(worker_job)
        else:
            worker_job.status = "complete" if succes else "failed"
            worker_job.worker_id = worker_id
            worker_job.nb_chunks_generes = nb_chunks if succes else 0
            worker_job.erreur = erreur if not succes else None
            worker_job.completed_at = datetime.utcnow()

        # Update Document is_embedded flag
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.is_embedded = succes

        self.db.commit()

        logger.info(
            f"Worker results saved for doc {doc_id}: success={succes}, chunks={nb_chunks}"
        )
