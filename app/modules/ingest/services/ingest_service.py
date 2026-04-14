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
        file_path: str = None,
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
                file_path=file_path,
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
                # Clean NUL characters which PostgreSQL doesn't support
                if texte_extrait:
                    texte_extrait = texte_extrait.replace("\x00", "")
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

                # Sanitize metadata from LLM (may return invalid types)
                if metadata:
                    raw_annee = metadata.get("annee")
                    if isinstance(raw_annee, int):
                        annee_val = raw_annee
                    elif isinstance(raw_annee, str):
                        import re as _re
                        _m = _re.search(r'(20\d{2})', str(raw_annee))
                        annee_val = int(_m.group(1)) if _m else 2026
                    else:
                        annee_val = 2026

                    raw_niveau = metadata.get("niveau", "")
                    if isinstance(raw_niveau, str):
                        raw_niveau = raw_niveau.strip() or "Non specifie"
                    else:
                        raw_niveau = "Non specifie"

                    raw_serie = metadata.get("serie")
                    if raw_serie is not None and isinstance(raw_serie, str):
                        raw_serie = raw_serie.strip() or None
                    if raw_serie is not None and not isinstance(raw_serie, str):
                        raw_serie = str(raw_serie)

                    raw_sous_type = metadata.get("sous_type")
                    if raw_sous_type is not None and isinstance(raw_sous_type, str):
                        raw_sous_type = raw_sous_type.strip() or None
                    if raw_sous_type is not None and not isinstance(raw_sous_type, str):
                        raw_sous_type = str(raw_sous_type) or None

                    raw_notion = metadata.get("notion_principale")
                    if raw_notion is not None and isinstance(raw_notion, str):
                        raw_notion = raw_notion.strip() or None
                    if raw_notion is not None and not isinstance(raw_notion, str):
                        raw_notion = str(raw_notion) or None

                    raw_diff = metadata.get("difficulte_estimee")
                    if raw_diff is not None and isinstance(raw_diff, str):
                        raw_diff = raw_diff.strip() or None
                    if raw_diff is not None and not isinstance(raw_diff, str):
                        raw_diff = str(raw_diff) or None

                    raw_mots = metadata.get("mots_cles", [])
                    if isinstance(raw_mots, str):
                        # Try to parse JSON string like "[]" or "[\"word\"]"
                        import json as _json2
                        try:
                            raw_mots = _json2.loads(raw_mots)
                        except Exception:
                            raw_mots = []
                    if not isinstance(raw_mots, list):
                        raw_mots = []

                    raw_type = metadata.get("type_doc", "epreuve")
                    if not isinstance(raw_type, str) or not raw_type:
                        raw_type = "epreuve"

                    raw_matiere = metadata.get("matiere", "Autre")
                    if not isinstance(raw_matiere, str) or not raw_matiere:
                        raw_matiere = "Autre"

                    raw_langue = metadata.get("langue", "fr")
                    if not isinstance(raw_langue, str) or not raw_langue:
                        raw_langue = "fr"
                    else:
                        # Truncate to 5 chars (column is VARCHAR(5))
                        raw_langue = raw_langue.strip()[:5]
                        if not raw_langue:
                            raw_langue = "fr"

                    raw_etablissement = metadata.get("etablissement")
                    if raw_etablissement is not None and isinstance(raw_etablissement, str):
                        raw_etablissement = raw_etablissement.strip() or None
                    if raw_etablissement is not None and not isinstance(raw_etablissement, str):
                        raw_etablissement = str(raw_etablissement) or None

                    raw_region = metadata.get("region")
                    if raw_region is not None and isinstance(raw_region, str):
                        raw_region = raw_region.strip() or None
                    if raw_region is not None and not isinstance(raw_region, str):
                        raw_region = str(raw_region) or None
                else:
                    annee_val = 2026
                    raw_niveau = "Non specifie"
                    raw_serie = None
                    raw_sous_type = None
                    raw_notion = None
                    raw_diff = None
                    raw_mots = []
                    raw_type = "epreuve"
                    raw_matiere = "Autre"
                    raw_langue = "fr"
                    raw_etablissement = None
                    raw_region = None

                file_data = {
                    "content": file_bytes,
                    "filename": nom_original,
                    "mimetype": "application/pdf",
                }
                doc_metadata = {
                    "chemin_final": chemin_final,
                    "nom_affiche": nom_original,
                    "matiere": raw_matiere,
                    "niveau": raw_niveau,
                    "serie": raw_serie,
                    "annee": annee_val,
                    "type_doc": raw_type,
                    "sous_type": raw_sous_type,
                    "notion_principale": raw_notion,
                    "mots_cles": raw_mots,
                    "is_validated": metadata_confidence >= 0.6 if metadata else False,
                    "difficulte_estimee": raw_diff,
                    "etablissement": raw_etablissement,
                    "region": raw_region,
                    "langue": raw_langue,
                }
                doc_result = asyncio.run(
                    doc_service.ajouter_document(
                        file_data=file_data,
                        metadata=doc_metadata,
                        uploaded_by=uploaded_by,
                    )
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

            # 9. Generate embeddings locally with FastEmbed
            try:
                self._generate_embeddings_local(doc_id, texte_extrait, nom_original, doc_obj)
            except Exception as exc:
                logger.warning(f"Local embedding failed for doc {doc_id}: {exc}")

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

    # ─── Local Embedding Generation ──────────────────────────────
    def _generate_embeddings_local(self, doc_id: int, texte_extrait: str, nom_original: str, doc_obj=None):
        """
        Generate embeddings locally with FastEmbed and store chunks in DB + Vespa.
        Replaces the external worker approach.
        """
        from app.modules.epreuves.models.document_chunk import DocumentChunk
        from app.modules.ingest.models import WorkerJob
        from fastembed import TextEmbedding
        import asyncio

        CHUNK_SIZE = 1500  # characters per chunk
        OVERLAP = 200  # overlap between chunks

        # 1. Split text into chunks
        chunks = []
        start = 0
        while start < len(texte_extrait):
            end = start + CHUNK_SIZE
            chunk_text = texte_extrait[start:end]
            chunks.append(chunk_text)
            start = end - OVERLAP
            if start >= len(texte_extrait) - CHUNK_SIZE:
                break

        if not chunks:
            logger.info(f"No text to embed for doc {doc_id}")
            return

        # 2. Generate embeddings with FastEmbed
        model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        embeddings = list(model.embed(chunks))

        # 3. Save chunks to DB
        chunk_records = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            nb_tokens = len(chunk_text.split())
            chunk_record = DocumentChunk(
                doc_id=doc_id,
                texte_chunk=chunk_text[:4000],  # limit DB size
                chunk_idx=idx,
                nb_tokens_estime=nb_tokens,
                is_embedded=True,
            )
            self.db.add(chunk_record)
            chunk_records.append(chunk_record)

        self.db.flush()

        # 4. Update Document.is_embedded
        if doc_obj is None:
            doc_obj = self.db.query(Document).filter(Document.id == doc_id).first()
        if doc_obj:
            doc_obj.is_embedded = True

        # 5. Send to Vespa (best effort)
        try:
            asyncio.run(self._send_to_vespa(doc_id, chunks, embeddings, nom_original, doc_obj))
        except Exception as exc:
            logger.warning(f"Vespa indexing failed for doc {doc_id}: {exc}")

        # 6. Create WorkerJob as complete (for API compatibility)
        worker_job = WorkerJob(
            document_id=doc_id,
            job_type="embed",
            status="complete",
            nb_chunks_generes=len(chunks),
        )
        self.db.add(worker_job)

        logger.info(f"Local embedding complete for doc {doc_id}: {len(chunks)} chunks")

    async def _send_to_vespa(self, doc_id: int, chunks: list, embeddings: list, nom_original: str, doc_obj):
        """Send chunks and embeddings to Vespa (best effort)."""
        try:
            import httpx
            vespa_url = "http://localhost:18080"
            async with httpx.AsyncClient(timeout=30.0) as client:
                for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                    vespa_doc = {
                        "put": f"id:epreuves:epreuve::{doc_id}_{idx}",
                        "fields": {
                            "doc_id": doc_id,
                            "chunk_idx": idx,
                            "content": chunk_text[:2000],
                            "nom_original": nom_original[:200],
                            "matiere": doc_obj.matiere or "Autre",
                            "niveau": doc_obj.niveau or "Non specifie",
                            "embedding": embedding.tolist(),
                        }
                    }
                    await client.post(f"{vespa_url}/document/v1/epreuves/epreuve/docid/{doc_id}_{idx}", json=vespa_doc)
            logger.info(f"Vespa indexing succeeded for doc {doc_id}: {len(chunks)} chunks")
        except Exception as exc:
            logger.warning(f"Vespa feed failed for doc {doc_id}: {exc}")
