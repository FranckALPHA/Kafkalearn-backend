# User Documents Module — Integration Guide

## Overview

The `user_documents` module manages personal document uploads, text extraction, vectorization, and RAG-ready access for users. It integrates with multiple other modules for storage, notifications, and skill-based queries.

---

## Endpoints

All endpoints are prefixed with `/user-documents` (or `/admin/user-documents`) and require authentication (JWT bearer token).

### User Documents (`/user-documents`)

| Method | Path | Status | Description | Rate Limit |
|--------|------|--------|-------------|------------|
| `POST` | `/user-documents/upload` | 201 | Upload a document (File + Form: titre, subject, class_name, language). Validates via FileValidator, checks quotas, saves, queues extraction. | 5/hour |
| `GET` | `/user-documents/` | 200 | List documents with filters: `subject`, `language`, `extraction_status`, `is_vectorized`, `page`, `limit`. Returns `DocumentListResponse`. | 60/min |
| `GET` | `/user-documents/stats` | 200 | User document stats: `nb_documents`, `nb_vectorises`, `espace_utilise`, `quota`, `taux_utilisation`, `document_plus_utilise`. | — |
| `GET` | `/user-documents/{document_id}` | 200 | Get detailed document info. Returns `DocumentDetailResponse`. | — |
| `PATCH` | `/user-documents/{document_id}` | 200 | Update document metadata (titre, subject, class_name, language). | — |
| `DELETE` | `/user-documents/{document_id}` | 204 | Delete document, associated chunks, and physical file. | — |
| `GET` | `/user-documents/{document_id}/download` | 200 | Stream/download the original file via `FileResponse`. | — |
| `POST` | `/user-documents/{document_id}/vectorize` | 202 | Trigger vectorization. Premium+ users only. | — |

### Admin (`/admin/user-documents`)

| Method | Path | Description | Access |
|--------|------|-------------|--------|
| `GET` | `/admin/user-documents/stats` | Global document statistics | SuperAdmin/Admin |
| `POST` | `/admin/user-documents/retry-extractions` | Re-process failed extractions from last 7 days | SuperAdmin/Admin |

---

## Cross-Module Contracts

### Skills Module

| Integration | Details |
|-------------|---------|
| **UserDocumentRAGService** | `obtenir_contexte_pour_rag(user_id, document_id, query, top_k)` — provides RAG context for skill queries. Returns chunks from vectorized documents or truncated text from non-vectorized docs. |
| **peut_utiliser_pour_rag** | Checks if a document is ready for RAG (extraction success + optional vectorization). |
| **utilisation tracking** | `incrementer_utilisation(document_id)` — increments `nb_utilisations_rag` and updates `derniere_utilisation_at`. |

### Calendar Module

| Integration | Details |
|-------------|---------|
| **Recent document suggestions** | Calendar suggestions may include recently uploaded/active user documents for study context. Documents queried via `UserDocument` model with `created_at` and `derniere_utilisation_at` filters. |

### Notifications Module

| Integration | Details |
|-------------|---------|
| **Extraction success** | `NotificationService.send_to_user()` sends `document_ready` type notification when text extraction completes. |
| **Vectorization success** | `NotificationService.send_to_user()` sends `document_vectorized` type notification when vectorization completes. |
| **Inactive documents** | `notify_inactive_documents_task` sends `document_inactive` notification to users with documents unused for 90+ days. |

### Users Module

| Integration | Details |
|-------------|---------|
| **Auth** | `get_current_user` from `app.modules.user_documents.routes.dependencies` — JWT bearer token, returns `User`. |
| **Quota verification** | `_verifier_quotas(user_id, new_file_bytes)` — checks user `plan_effectif` against `PLAN_QUOTAS` (max documents and max bytes per plan). |
| **DB** | `get_db` from `app.core.database` via `SessionLocal`. |
| **Rate Limiter** | `RateLimiter` from `app.modules.users.utils.rate_limiter`. |
| **User model** | `User.id`, `User.plan_effectif`, `User.is_active`, `User.role` queried during upload, deletion, and admin operations. |

### Library Module (Storage)

| Integration | Details |
|-------------|---------|
| **StorageService** | `StorageService` from `app.modules.library.utils.storage_service` used for saving, reading, and deleting uploaded files in `USER_DOCS_UPLOAD_DIR`. |

---

## Celery Tasks

| Task Name | Queue | Description |
|-----------|-------|-------------|
| `user_documents.tasks.extract_document_text` | default | Extract text from uploaded document (PDF via pdfplumber). Retries up to 3 times. |
| `user_documents.tasks.vectorize_document` | default | Vectorize document for semantic search (placeholder — sets status=complete). Retries up to 3 times. |
| `user_documents.tasks.cleanup_orphan_files` | cron | Remove physical files without corresponding DB entries. Weekly (Sunday 4h30). |
| `user_documents.tasks.notify_inactive_documents` | cron | Notify users about documents unused for 90+ days. Monthly (1st of month 5h30). |
| `user_documents.tasks.retry_failed_extractions_cron` | cron | Retry failed extractions from last 7 days. Every 3h30. |

---

## Models

| Model | Table | Purpose |
|-------|-------|---------|
| `UserDocument` | `user_documents` | User-uploaded documents with extraction status, vectorization status, and usage tracking. |
| `UserDocumentChunk` | `user_document_chunks` | Text chunks from document extraction with optional embeddings. |

---

## Services

| Service | Purpose |
|---------|---------|
| `UserDocumentService` | Upload validation, quota checks, dedup, listing, deletion, ownership verification. |
| `UserDocumentExtractorService` | Text extraction from PDFs, retry failed extractions, queue vectorization. |
| `UserDocumentRAGService` | RAG context retrieval for skill queries, RAG readiness checks. |

---

## Schemas

| Schema | Purpose |
|--------|---------|
| `DocumentUpdateRequest` | PATCH request body: `titre`, `subject`, `class_name`, `language`. |
| `DocumentListResponse` | GET / response: `total`, `espace_utilise_bytes`, `espace_quota_bytes`, `documents`. |
| `DocumentDetailResponse` | GET /{id} response: full document metadata including extraction and vectorization status. |

---

## Rate Limiters

| Limiter | Max Requests | Window | Used By |
|---------|-------------|--------|---------|
| `upload_rate_limiter` | 5 | 3600s (1 hour) | POST /upload |
| `documents_list_rate_limiter` | 60 | 60s | GET / |
