import json
import logging
import os
import uuid
from datetime import datetime

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.ingest.services.base import IngestBaseService

logger = logging.getLogger(__name__)


class IngestService(IngestBaseService):
    def __init__(self, db: Session, redis: Redis = None, storage_service=None):
        super().__init__(db, redis)
        self.storage = storage_service

    async def ingerer_fichier_async(
        self,
        file_bytes: bytes,
        nom_original: str,
        uploaded_by,
        force_metadata: dict = None,
    ) -> dict:
        """Create an IngestJob and queue a Celery task for async processing."""
        from app.modules.ingest.models import IngestJob

        job_id = str(uuid.uuid4())
        job = IngestJob(
            id=job_id,
            initiated_by=uploaded_by,
            job_type="single_file",
            status="pending",
            nb_fichiers_total=1,
        )
        self.db.add(job)
        self.db.commit()

        try:
            from app.modules.ingest.jobs.tasks import process_single_ingest_task

            process_single_ingest_task.delay(
                job_id=job_id,
                file_bytes_b64=None,
                nom_original=nom_original,
                uploaded_by=str(uploaded_by),
                force_metadata=force_metadata,
            )
        except Exception as exc:
            logger.error(f"Failed to queue Celery task for job {job_id}: {exc}")
            job.status = "failed"
            job.erreurs_detail = [{"error": str(exc), "timestamp": datetime.utcnow().isoformat()}]
            self.db.commit()

        return {
            "job_id": job_id,
            "message": "Ingestion queued",
            "status_url": f"/ingest/jobs/{job_id}",
        }

    def process_single_ingest_sync(
        self,
        job_id: str,
        file_path: str,
        nom_original: str,
        uploaded_by,
        force_metadata: dict = None,
    ) -> dict:
        """Sync method called by Celery worker to process a single file ingestion."""
        from app.modules.ingest.models import IngestJob
        from app.modules.ingest.utils import FileSecurity, DocConverter

        job = self.db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            raise ValueError(f"IngestJob {job_id} not found")

        try:
            job.status = "running"
            job.started_at = datetime.utcnow()
            self.db.commit()

            # Read file bytes
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            # 1. Validate file via FileSecurity
            file_type = FileSecurity.validate_magic_bytes(file_bytes)

            # 2. Convert DOCX to PDF if needed
            if file_type == "docx":
                converter = DocConverter()
                file_bytes = converter.convert_docx_to_pdf(file_bytes)
                file_type = "pdf"

            # 3. Check hash for duplicates
            from app.modules.epreuves.utils.hash_utils import sha256_bytes

            content_hash = sha256_bytes(file_bytes)
            from app.modules.epreuves.models import Document

            existing = self.db.query(Document).filter(Document.hash_contenu == content_hash).first()
            if existing:
                job.status = "complete"
                job.nb_traites = 1
                job.nb_doublons = 1
                job.completed_at = datetime.utcnow()
                self.db.commit()
                return {
                    "document_id": existing.id,
                    "is_duplicate": True,
                    "job_id": job_id,
                }

            # 4. Extract text via PipelineExtraction
            texte_extrait = None
            try:
                from app.modules.user_documents.services.pipeline_extraction import (
                    PipelineExtraction,
                )

                pipeline = PipelineExtraction()
                texte_extrait = pipeline.extraire_texte(file_bytes, file_type)
            except Exception as exc:
                logger.warning(f"Text extraction failed for {nom_original}: {exc}")
                texte_extrait = ""

            # 5. Extract metadata via MetadataParserService or use force_metadata
            metadata = force_metadata
            metadata_confidence = 1.0
            if metadata is None:
                try:
                    import asyncio

                    from app.modules.ingest.services.metadata_parser_service import (
                        MetadataParserService,
                    )

                    parser = MetadataParserService(db=self.db, redis=self.redis)
                    loop = asyncio.new_event_loop()
                    metadata, metadata_confidence = loop.run_until_complete(
                        parser.extraire_metadata(texte_extrait or "", nom_original)
                    )
                    loop.close()
                except Exception as exc:
                    logger.warning(f"Metadata extraction failed for {nom_original}: {exc}")
                    metadata = {}
                    metadata_confidence = 0.0

            # 6. Save file via storage service
            if self.storage is None:
                from app.modules.epreuves.utils.storage import StorageService

                self.storage = StorageService()

            relative_path = f"{metadata.get('matiere', 'autre') if metadata else 'autre'}/{content_hash[:8]}_{nom_original}"
            chemin_final = self.storage.save_file_sync(
                file_bytes=file_bytes,
                relative_path=relative_path,
                mimetype="application/pdf",
            )

            # 7. Create Document via DocumentService
            try:
                from app.modules.epreuves.services.document_service import DocumentService

                doc_service = DocumentService(db=self.db, redis=self.redis)
                file_data = {
                    "content": file_bytes,
                    "filename": nom_original,
                    "mimetype": "application/pdf",
                }
                doc_metadata = {
                    "chemin_final": chemin_final,
                    "nom_affiche": nom_original,
                    "matiere": metadata.get("matiere", "Autre") if metadata else "Autre",
                    "niveau": metadata.get("niveau", "Non specifie") if metadata else "Non specifie",
                    "serie": metadata.get("serie") if metadata else None,
                    "annee": metadata.get("annee", 2026) if metadata else 2026,
                    "type_doc": metadata.get("type_doc", "epreuve") if metadata else "epreuve",
                    "sous_type": metadata.get("sous_type") if metadata else None,
                    "notion_principale": metadata.get("notion_principale") if metadata else None,
                    "mots_cles": metadata.get("mots_cles", []) if metadata else [],
                    "is_validated": metadata_confidence >= 0.6 if metadata else False,
                    "difficulte_estimee": metadata.get("difficulte_estimee") if metadata else None,
                    "etablissement": metadata.get("etablissement") if metadata else None,
                    "region": metadata.get("region") if metadata else None,
                    "langue": metadata.get("langue", "fr") if metadata else "fr",
                }
                doc_result = doc_service.ajouter_document(
                    file_data=file_data,
                    metadata=doc_metadata,
                    uploaded_by=uploaded_by,
                )
                doc_id = doc_result["document_id"]
            except Exception as exc:
                logger.error(f"Document creation failed for {nom_original}: {exc}")
                raise

            # 8. Index in MeiliSearch
            try:
                from app.modules.epreuves.utils.meilisearch_client import MeiliClient

                meili = MeiliClient(self.redis)
                doc_obj = self.db.query(Document).filter(Document.id == doc_id).first()
                if doc_obj and meili.available:
                    meili.index_document(doc_obj.serialize_list_item())
            except Exception as exc:
                logger.warning(f"MeiliSearch indexing failed for doc {doc_id}: {exc}")

            # 9. Create WorkerJob for Vespa embedding
            try:
                from app.modules.ingest.models import WorkerJob

                worker_job = WorkerJob(
                    document_id=doc_id,
                    job_type="embed",
                    status="pending",
                )
                self.db.add(worker_job)
            except Exception as exc:
                logger.warning(f"WorkerJob creation failed for doc {doc_id}: {exc}")

            # 10. Update text extract on document
            doc_obj = self.db.query(Document).filter(Document.id == doc_id).first()
            if doc_obj and texte_extrait:
                doc_obj.texte_extrait = texte_extrait

            # 11. Update Document metadata confidence
            if doc_obj:
                doc_obj.metadata_confidence = metadata_confidence
                doc_obj.ingest_status = "completed"

            # 12. If metadata confidence < 0.6, queue to MetadataQueueService
            if metadata_confidence < 0.6:
                try:
                    from app.modules.ingest.services.metadata_queue_service import (
                        MetadataQueueService,
                    )

                    queue_service = MetadataQueueService(db=self.db, redis=self.redis)
                    queue_service.mettre_en_attente(
                        fichier_path=chemin_final,
                        raison="low_confidence",
                        metadata_tentee=metadata,
                        texte_preview=(texte_extrait or "")[:500],
                    )
                except Exception as exc:
                    logger.warning(f"MetadataQueueService failed: {exc}")

            # 13. Auto-generate memory items (flashcards, QCM) from document text
            if texte_extrait and len(texte_extrait) > 100:
                try:
                    from app.modules.memory.jobs.tasks import generate_memory_items_task
                    section_title = metadata.get("notion_principale", "Contenu principal") if metadata else "Contenu principal"
                    generate_memory_items_task.delay(
                        document_id=doc_id,
                        section_title=section_title,
                        texte_section=texte_extrait[:5000],
                        langue=metadata.get("langue", "fr") if metadata else "fr",
                    )
                    logger.info(f"Memory generation task queued for doc {doc_id}")
                except Exception as exc:
                    logger.warning(f"Memory generation queue failed for doc {doc_id}: {exc}")

            # Update job success
            job.nb_traites = 1
            job.nb_succes = 1
            job.status = "complete"
            job.completed_at = datetime.utcnow()
            self.db.commit()

            return {
                "document_id": doc_id,
                "is_duplicate": False,
                "job_id": job_id,
            }

        except Exception as exc:
            logger.error(f"Ingestion failed for job {job_id}: {exc}", exc_info=True)
            job.status = "failed"
            job.nb_traites = (job.nb_traites or 0) + 1
            job.nb_echecs = (job.nb_echecs or 0) + 1
            if job.erreurs_detail is None:
                job.erreurs_detail = []
            if isinstance(job.erreurs_detail, list):
                job.erreurs_detail.append(
                    {"error": str(exc), "timestamp": datetime.utcnow().isoformat()}
                )
            job.completed_at = datetime.utcnow()
            self.db.commit()
            raise
