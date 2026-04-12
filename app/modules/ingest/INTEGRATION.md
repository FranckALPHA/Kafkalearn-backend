# Ingest Module - Integration Contracts

## Overview

The `ingest` module handles document ingestion, embedding coordination, and metadata extraction for the KafkaLearn platform. It orchestrates file upload, text extraction, metadata parsing, document creation, search indexing, Vespa embedding, and metadata quality management.

---

## Endpoints

### Admin Endpoints (prefix: `/ingest`, SuperAdmin/Admin only)

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `POST` | `/ingest/indexer-async` | 202 | Upload a file and queue it for async ingestion. Returns `{job_id, message, status_url}`. |
| `GET` | `/ingest/indexer-report/{job_id}` | 200 | Get progress report for an ingest job. Returns `IngestReportResponse`. |
| `POST` | `/ingest/scan-folder` | 202 | Launch async folder scan. Accepts `FolderScanRequest` (`chemin_dossier`). Returns `{scan_id, message}`. |
| `GET` | `/ingest/metadata-queue` | 200 | List unresolved metadata queue entries. Returns `{entries, total}`. |
| `POST` | `/ingest/metadata-queue/{queue_id}/resolve` | 200 | Manually resolve a metadata queue entry with provided metadata dict. |

### Worker Endpoints (prefix: `/ingest/worker`, protected by `X-Worker-Token` header)

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `GET` | `/ingest/worker/not-embedded` | 200 | Get list of documents pending embedding. Returns `WorkerChunkResponse` (`documents`). |
| `POST` | `/ingest/worker/save-results/{doc_id}` | 200 | Save worker embedding results. Accepts `WorkerResultRequest` (`worker_id, succes, nb_chunks_embeds, erreur`). |

---

## Cross-Module Contracts

### 1. `epreuves` (DocumentService)

- **Document creation**: `IngestService.process_single_ingest_sync` calls `DocumentService.ajouter_document()` from `app.modules.epreuves.services.document_service` to create `Document` records.
- **Document model**: Uses `Document` from `app.modules.epreuves.models` for duplicate detection (via `hash_contenu`), text extract storage (`texte_extrait`), and embedding flags (`is_embedded`, `ingest_status`).
- **Storage**: Uses `StorageService` from `app.modules.epreuves.utils.storage` for file persistence.
- **Hash utils**: Uses `sha256_bytes` from `app.modules.epreuves.utils.hash_utils` for duplicate detection.

### 2. `search` (MeiliSearch)

- **Indexing**: After document creation, `IngestService` calls `MeiliClient.index_document()` from `app.modules.epreuves.utils.meilisearch_client` to index the new document in MeiliSearch.
- **Filter cache invalidation**: When documents are re-ingested or updated, search filter caches should be invalidated. The ingest module does not directly invalidate caches -- consumers of the search module should listen for document creation/update events.

### 3. `doc_analysis`

- **Cache invalidation on re-ingest**: When a document is re-ingested (force re-upload), any cached analysis results in the `doc_analysis` module should be invalidated. The ingest module sets `ingest_status = "completed"` on the `Document` which can be used as a signal for cache invalidation.

### 4. `core/extract` (Text Extraction)

- **PipelineExtraction**: `IngestService.process_single_ingest_sync` uses `PipelineExtraction` from `app.modules.user_documents.services.pipeline_extraction` to extract text from uploaded files (PDF, DOCX, etc.).
- **File conversion**: Uses `DocConverter` from `app.modules.ingest.utils` for DOCX-to-PDF conversion before text extraction.

### 5. `core/llm` (Metadata Classification)

- **MetadataParserService**: `IngestService` calls `MetadataParserService.extraire_metadata()` from `app.modules.ingest.services.metadata_parser_service` which uses LLM providers to extract metadata (matiere, niveau, serie, type_doc, etc.) from document text.
- **Confidence threshold**: Metadata with `metadata_confidence < 0.6` is queued to `MetadataQueueService` for manual review or reprocessing.

---

## Celery Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `process_single_ingest_task` | On-demand (via `delay()`) | Process a single file ingestion. Called after file upload. |
| `reprocess_metadata_queue_task` | Every 2 hours | Retry unresolved metadata queue entries (max 3 retries unless `force=True`). |
| `audit_pipeline_health_task` | Every 7 hours | Check for stuck jobs, failed workers. Returns health report. |
| `check_stuck_workers_task` | Every 30 minutes | Find `WorkerJob` entries stuck in `"processing"` for > 2h and mark them `"failed"`. |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_TOKEN` | `"default-worker-token"` | Token required in `X-Worker-Token` header for worker endpoints. |
| `INGEST_CRON_SECRET` | `"default-cron-secret"` | Token required in `X-Cron-Secret` header for cron-triggered tasks. |
| `REDIS_URL` | (from config) | Broker and backend for Celery. |

---

## Data Flow

```
Upload File (POST /ingest/indexer-async)
  -> IngestService.ingerer_fichier_async()
    -> Create IngestJob (status: pending)
    -> Queue Celery task: process_single_ingest_task

Celery Worker: process_single_ingest_task
  -> IngestService.process_single_ingest_sync()
    1. FileSecurity.validate_magic_bytes()
    2. DocConverter.convert_docx_to_pdf() (if needed)
    3. sha256_bytes() -> duplicate check
    4. PipelineExtraction.extraire_texte()
    5. MetadataParserService.extraire_metadata() (or use force_metadata)
    6. StorageService.save_file_sync()
    7. DocumentService.ajouter_document() -> Document created
    8. MeiliClient.index_document() -> indexed in search
    9. Create WorkerJob (job_type: embed, status: pending)
    10. If metadata_confidence < 0.6 -> MetadataQueueService.mettre_en_attente()
    11. Update IngestJob (status: complete)

Worker: GET /ingest/worker/not-embedded
  -> WorkerCoordinatorService.lister_documents_a_embedder()
  -> Returns documents with texte_extrait ready for embedding

Worker: POST /ingest/worker/save-results/{doc_id}
  -> WorkerCoordinatorService.sauvegarder_resultats_worker()
  -> Updates WorkerJob status and Document.is_embedded
```

---

## Models

| Model | Table | Description |
|-------|-------|-------------|
| `IngestJob` | `ingest_jobs` | Tracks ingestion jobs (single file, folder scan, etc.). |
| `WorkerJob` | `worker_jobs` | Tracks embedding/OCR jobs dispatched to external workers. |
| `MetadataQueue` | `metadata_queue` | Queues documents with low-confidence metadata for reprocessing or manual review. |
