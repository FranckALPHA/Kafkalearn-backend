# Document Analysis Module - Integration Guide

## Module Overview

The `doc_analysis` module provides LLM-powered analysis of documents (epreuves/lecons),
caching, feedback collection, and admin quality monitoring.

---

## Endpoints

### Analysis Routes (`/documents`)

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| POST | `/documents/analyze` | Analyze a document (returns cached or generates). Body: `document_id` (query), `langue` (query, default "fr"). | Required (access token) | 30/min |
| GET | `/documents/analyze/{document_id}` | Get cached analysis only. Returns 404 if not exists. Query: `langue` (default "fr"). | Required (access token) | None |
| POST | `/documents/analyze/{document_id}/refresh` | Force regeneration of analysis. Query: `langue` (default "fr"). | Required, **Premium+** | 1/24h per user+doc |
| POST | `/documents/analyze/{document_id}/feedback` | Submit feedback on analysis. Body: `FeedbackRequest`. | Required (access token) | 10/min |

### Admin Routes (`/admin/doc-analysis`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/admin/doc-analysis/stats` | Global cache statistics (total analyses, accesses, feedback, quality metrics). | SuperAdmin only |
| GET | `/admin/doc-analysis/low-quality` | List of analyses with low quality (utility rate < threshold). Query: `seuil` (default 0.35), `min_feedbacks` (default 5). | SuperAdmin only |

---

## Integration Contracts

### 1. Epreuves Module (Invalidation on Document Update)

When a document is updated in the epreuves module, the associated analyses must be invalidated:

```python
from app.modules.doc_analysis.services.analysis_cache_service import AnalysisCacheService

cache_service = AnalysisCacheService(db=db)
invalidated_count = await cache_service.invalider_analyses_document(document_id)
```

**Trigger points:**
- Document text update (`texte_extrait` changes)
- Document deletion (cascade via FK `ondelete="CASCADE"`)
- Document type/matiere change that affects analysis relevance

### 2. Memory Module (Enrichment with Analysis Concepts)

The memory module can consume analysis concepts to enrich user learning profiles:

```python
from app.modules.doc_analysis.models import DocumentAnalysis

analysis = db.query(DocumentAnalysis).filter(
    DocumentAnalysis.document_id == document_id,
    DocumentAnalysis.langue == user_langue,
).first()

# Extract concepts for memory enrichment
concepts = analysis.concepts or []       # Key concepts identified
key_points = analysis.key_points or []   # Main points
notions = analysis.notions_prerequis or []  # Prerequisite notions
```

### 3. Notifications Module (Quality Alerts to Admins)

When an analysis falls below the quality threshold, notify admins:

```python
from app.modules.doc_analysis.services.analysis_feedback_service import AnalysisFeedbackService

# After recording feedback, the service internally checks the alert threshold
# (ALERT_THRESHOLD_RATE, MIN_FEEDBACKS_FOR_ALERT in utils/constants.py)
# The service logs a warning; the notifications module can subscribe to this event.
```

**Integration pattern:** Subscribe to the `AnalysisFeedbackService._verifier_seuil_alerte` warning
and send a notification to superadmin users when triggered.

### 4. Core LLM (Analysis Generation)

Analysis generation uses `LLMClient` from the skills module:

```python
from app.modules.skills.utils.llm_client import LLMClient
from app.modules.doc_analysis.utils import PromptBuilder

llm_client = LLMClient()
system_prompt = PromptBuilder.build_system_prompt(analysis_type, langue)
user_prompt = PromptBuilder.build_user_prompt(document_dict)
raw_response = await llm_client.generate(system_prompt, user_prompt)
```

The analysis service handles:
- Prompt construction (via `PromptBuilder`)
- LLM call with provider fallback
- JSON validation (via `JSONValidator`)
- Hash computation for cache coherence (via `HashUtils`)

---

## Celery Tasks

| Task | Queue | Schedule | Description |
|------|-------|----------|-------------|
| `increment_analysis_access` | default | On-demand | Increment `nb_acces` on `DocumentAnalysis` |
| `analyze_missing_documents` | heavy | Every 1h30 | Pre-heat cache for documents without analyses |
| `verify_cache_coherence` | default | Weekly (Sunday 3h) | Check hash coherence, invalidate obsolete analyses |
| `flush_access_counters` | default | Every 15min | Flush Redis access counters to DB |

---

## Database Models

- **`DocumentAnalysis`** (`document_analyses` table): Stores LLM-generated analyses with caching metadata.
- **`AnalysisFeedback`** (`analysis_feedbacks` table): Stores user feedback on analyses.

## Schemas

### Request
- `FeedbackRequest`: `est_utile: bool`, `langue?: str`, `section_problematique?: str`, `commentaire?: str`

### Response
- `AnalysisResponse`: `document_id`, `langue`, `analysis_type`, `key_points`, `concepts`, `tips`, `summary`, `methodologie`, `notions_prerequis`, `is_cached`, `analyzed_at`, `nb_acces`
- `FeedbackResponse`: `message`, `taux_utilite_actuel?`

---

## Configuration Constants

See `app/modules/doc_analysis/utils/constants.py`:
- `REFRESH_TTL_SECONDS`: TTL for refresh rate limit (default 86400 = 24h)
- `ALERT_THRESHOLD_RATE`: Threshold for low-quality alerts
- `MIN_FEEDBACKS_FOR_ALERT`: Minimum feedbacks before triggering quality alert

---

## Setup

1. Register the router in `app/main.py`:
   ```python
   from app.modules.doc_analysis.router import router as doc_analysis_router
   app.include_router(doc_analysis_router, prefix="/api/v1")
   ```

2. Add Celery beat schedule in your Celery config:
   ```python
   from app.modules.doc_analysis.jobs.crons import beat_schedule
   celery_app.conf.beat_schedule.update(beat_schedule)
   ```

3. Run Celery worker with the `default` and `heavy` queues:
   ```bash
   celery -A app.modules.doc_analysis.jobs.celery_app.celery_app worker -Q default,heavy -l info
   ```
