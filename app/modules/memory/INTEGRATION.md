# Memory Module — Integration Guide

## Overview

The `memory` module implements spaced repetition learning via SM-2 algorithm. It generates memory items (flashcards, QCM, cloze, short_answer) from lesson documents, tracks user progress, and schedules reviews.

---

## Cross-Module Contracts

### 1. Epreuves Module
- **Input**: `Document` records of type `lecon` are required for memory generation.
- `MemoryGeneratorService.generer_pack_section` validates `doc.type_doc == "lecon"`.
- Section summaries come from the lesson's extracted text.

### 2. Users Module
- **Authentication**: All user routes require a valid JWT access token via `get_current_user`.
- **Progress logging**: `UserSectionProgress` tracks per-user per-section progress, scores, and SM-2 scheduling.
- **Rate limiting**: Uses `RateLimiter` from `app.modules.users.utils.rate_limiter`.
- **Streak**: Reads `user.streak` for the stats endpoint.

### 3. Notifications Module
- **Review reminders**: `send_review_reminder_task` calls `NotificationService.send_notification`.
- If the notifications module is unavailable, tasks gracefully skip with a logged warning.

### 4. Calendar Module
- **Daily suggestions**: The calendar module should query `GET /memory/today` to include due review sections in daily study plans.
- `ReviewTodayResponse` provides `nb_sections_a_revoir`, `temps_estime_minutes`, and per-section urgency.

### 5. Library Module
- **MEMORY_PACK assets**: When a section is generated, the library module can store a `MEMORY_PACK` asset linked to the `MemorySection.asset_id`.
- Assets are used for offline access and content caching.

---

## Endpoints

### User Routes (`/memory`)

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| `GET` | `/memory/sections?document_id={id}` | List sections for a document with user progress | Required | 60 req/min |
| `GET` | `/memory/sections/{section_id}/items` | Get items for review (no verso/answer) | Required | 60 req/min |
| `GET` | `/memory/sections/{section_id}/items/{item_id}/verso` | Reveal flashcard answer | Required | 60 req/min |
| `POST` | `/memory/sections/{section_id}/items/{item_id}/repondre` | Submit answer, get graded | Required | 30 req/min |
| `POST` | `/memory/sections/{section_id}/complete` | Mark section completed, schedule next review | Required | 30 req/min |
| `GET` | `/memory/today` | Sections due for review today | Required | 60 req/min |
| `GET` | `/memory/stats` | User memory statistics | Required | 60 req/min |

### Admin Routes (`/admin/memory`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/admin/memory/stats` | Global memory statistics | SuperAdmin |
| `POST` | `/admin/memory/regenerate/{section_id}` | Regenerate a section's items | SuperAdmin |

---

## Request/Response Schemas

### AnswerSubmitRequest
```json
{
  "reponse": "string (max 2000 chars, optional)",
  "qualite": 0,
  "duree_secondes": 30
}
```

### SectionCompleteRequest
```json
{}
```

### SectionListResponse
```json
{
  "document_id": 1,
  "document_titre": "Chapter 1",
  "nb_sections": 5,
  "progression_globale": 60.0,
  "sections": [{...}]
}
```

### SectionItemsResponse
```json
{
  "section_id": 1,
  "section_title": "Introduction",
  "nb_items": 20,
  "langue": "fr",
  "current_index": 3,
  "items": [{...}]
}
```

### ReviewTodayResponse
```json
{
  "nb_sections_a_revoir": 3,
  "temps_estime_minutes": 45,
  "sections": [{...}]
}
```

### MemoryStatsResponse
```json
{
  "total_sections": 10,
  "completed_sections": 4,
  "avg_score": 3.5,
  "total_reviews": 150,
  "accuracy": 0.72,
  "streak": 7,
  "next_reviews_due": 3,
  "top_weak_subjects": ["Algebra", "Geometry"]
}
```

---

## Celery Tasks

| Task | Description | Trigger |
|------|-------------|---------|
| `generate_memory_items_task` | Generate memory items for a section | Manual / Epreuves pipeline |
| `send_review_reminder_task` | Send review reminder to a user | Scheduled / Manual |
| `send_daily_review_reminders_task` | Send daily reminders to all users with due sections | Cron: daily 7:30 |
| `regenerate_weekly_packs_task` | Regenerate packs older than 7 days | Cron: Monday 2:00 |
| `update_item_difficulty_task` | Recalculate item difficulty from recent attempts | Cron: Wednesday 3:00 |
| `cleanup_orphans_monthly` | Clean up orphaned records | Cron: 1st of month 4:00 |

---

## Error Codes

| Code | Meaning |
|------|---------|
| `SECTION_NOT_FOUND` | Memory section does not exist |
| `ITEM_NOT_FOUND` | Memory item does not exist or doesn't belong to section |
| `PROGRESS_NOT_FOUND` | No user progress record for this section |
| `SUPERADMIN_REQUIRED` | User is not a superadmin |
| `RATE_LIMIT_EXCEEDED` | Too many requests |
| `INVALID_TOKEN` | JWT token is invalid or expired |
| `USER_NOT_FOUND` | User does not exist or is inactive |
