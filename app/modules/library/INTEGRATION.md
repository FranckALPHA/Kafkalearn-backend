# Library Module - Integration Guide

## Overview

The `library` module manages pedagogical assets (FICHE, QUIZ, CORRIGE, EPREUVE, SOLVER, MEMORY_PACK, VISUALISATION) with sharing, rating, copying, and recommendation features.

---

## Integration Contracts

### 1. Skills Module — `sauvegarder_asset`

After a skill generates an asset (e.g., a QUIZ or FICHE), it should call:

```python
from app.modules.library.services.pedagogical_asset_service import PedagogicalAssetService

asset_service = PedagogicalAssetService(db=db)
asset, was_duplicate = await asset_service.sauvegarder_asset(
    user_id=user.id,
    titre="Generated Title",
    asset_type="QUIZ",
    subject="Mathematiques",
    class_name="Terminale",
    serie="D",
    notion="Integration",
    content_json={"questions": [...]},
    file_url="/storage/quizzes/file.pdf",
    langue="fr",
    required_plan="access",
    source_doc_id=doc_id,
)
```

**Contract:**
- Skills must provide `titre`, `asset_type`, `user_id` at minimum.
- `content_json` contains the skill's structured output.
- `file_url` is the path to the generated file (if any).
- The service handles deduplication (same `user_id + titre + asset_type`).
- Returns `(asset, was_duplicate)`.

---

### 2. Memory Module — `MEMORY_PACK` Creation

When a user creates a MEMORY_PACK via the memory module:

```python
asset, _ = await asset_service.sauvegarder_asset(
    user_id=user.id,
    titre="Memory Pack: Notion X",
    asset_type="MEMORY_PACK",
    subject="Physique",
    class_name="Premiere",
    notion="Mecanique",
    content_json={"cards": [...]},
    required_plan="access",
)
```

**Contract:**
- `asset_type` must be `"MEMORY_PACK"`.
- `content_json` contains the flashcard data structure.
- Memory module can later query the library for the user's memory packs.

---

### 3. Calendar Module — Recent Personal Assets in Suggestions

The calendar module can fetch recent personal assets to suggest for study sessions:

```python
# GET /library/?tri=date_desc&limit=10
# Returns the user's 10 most recent assets
```

**Contract:**
- Calendar calls `GET /library/` with `tri=date_desc` and a small `limit`.
- Filters by `asset_type` if only specific types are needed (e.g., `?asset_type=QUIZ`).
- Response includes `created_at`, `titre`, `asset_type`, `subject`, `notion`.

---

### 4. Epreuves Module — `derived_assets` from Document

When a document in epreuves is processed and generates derived assets (QUIZ, CORRIGE, etc.):

```python
asset, _ = await asset_service.sauvegarder_asset(
    user_id=user.id,
    titre="Corrige: Epreuve 2024",
    asset_type="CORRIGE",
    subject="Mathematiques",
    class_name="Terminale",
    serie="C",
    content_json={"solutions": [...]},
    file_url="/storage/corriges/file.pdf",
    source_doc_id=document_id,  # Links back to the original epreuve document
    required_plan="access",
)
```

**Contract:**
- `source_doc_id` links the asset back to the original epreuve document.
- `asset_type` reflects the derived type (QUIZ, CORRIGE, etc.).
- The epreuves module can query library assets by `source_doc_id` to find all derived assets.

---

## API Endpoints

### Personal Assets (`/library`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/library/` | List personal assets (filters: `asset_type`, `subject`, `search`, `tri`, `page`, `limit`) | Required |
| GET | `/library/{asset_id}` | Get asset detail (with access checks) | Required |
| PATCH | `/library/{asset_id}` | Update asset metadata (`titre`, `subject`, `class_name`, `serie`, `notion`) | Required |
| DELETE | `/library/{asset_id}` | Delete asset (204) | Required |
| POST | `/library/{asset_id}/share` | Share/unshare asset (`is_public` bool) | Required |

### Public/Community (`/library/public`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/library/public/` | Explore community assets (filters: `asset_type`, `subject`, `class_name`, `search`, `tri`, `page`, `limit`) | Optional |
| GET | `/library/public/recommandes` | Personalized recommendations for current user | Required |
| GET | `/library/public/{share_code}` | Access asset by share code (format: `AST-XXXXXX`) | Required |

### Interactions (`/library/interactions`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/library/interactions/{asset_id}/copy` | Copy public asset to user's library (201) | Required |
| POST | `/library/interactions/{asset_id}/rate` | Rate public asset (`note` 1-5, optional `commentaire`) | Required |

### Admin (`/admin/library`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/admin/library/stats` | Global library stats (SuperAdmin only) | SuperAdmin |
| GET | `/admin/library/top` | Top-rated assets (SuperAdmin only) | SuperAdmin |

---

## Background Jobs (Celery)

| Task | Schedule | Description |
|------|----------|-------------|
| `increment_asset_stat_task` | On-demand (via `recuperer_par_id`) | Atomic increment of `nb_vues`/`nb_telechargements` |
| `recalculate_avg_ratings_task` | Every 4 hours | Recalculates `note_moyenne` for all rated assets |
| `cleanup_failed_assets_task` | Weekly (Monday 5h) | Soft-deletes assets in `failed` status older than 24h |
| `calculate_admin_stats_task` | Daily (2h) | Calculates global stats, caches in Redis 24h |
| `cleanup_orphan_copies_task` | Monthly (1st at 6h) | Removes `AssetCopy` entries where `copy_asset_id` no longer exists |

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/library/*` (general) | 60 requests | 60s |
| `/library/public/` (explore) | 30 requests | 60s |
| `/library/interactions/{id}/copy` | 10 requests | 60s |
| `/library/interactions/{id}/rate` | 5 requests | 60s |

---

## Models

- **`PedagogicalAsset`** — Main asset model with metadata, stats, sharing, and generation status.
- **`AssetRating`** — User ratings (1-5) with optional comments; unique per `(asset_id, user_id)`.
- **`AssetCopy`** — Tracks copies of public assets; unique per `(original_asset_id, copied_by)`.

---

## Services

- **`PedagogicalAssetService`** — Core service: save, list, detail, share, copy, delete, explore.
- **`AssetRatingService`** — Rating management and average recalculation.
- **`AssetRecommendationService`** — Personalized recommendations (lacunes, popular, recent).
- **`LibraryStatsService`** — Global statistics and top assets.

---

## Utilities

- **`ShareCodeGenerator`** — Generates unique share codes (format: `AST-XXXXXX`).
- **`StorageService`** — File operations (size, delete).
- **`Pseudonymizer`** — Anonymizes author names in public views.
- **`constants.py`** — `ASSET_TYPES`, `PLAN_HIERARCHY`, `PLAN_REQUIREMENTS`.
