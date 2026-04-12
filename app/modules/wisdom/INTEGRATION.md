# Wisdom Module - Integration Guide

## Overview

The `wisdom` module provides daily wisdom tips for students, with rating, sharing, and analytics capabilities.

## Endpoints

### Public Routes (prefix: `/wisdom`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/wisdom/daily` | Optional | Get today's wisdom tip. Marks as seen if authenticated user views it for the first time. Query param: `langue` (default: `fr`). |
| POST | `/wisdom/daily/rate` | Required | Rate today's wisdom tip (1-5). Body: `rating` (int). |
| POST | `/wisdom/daily/share` | Required | Record a share of today's wisdom and return formatted share text. |

### Admin Routes (prefix: `/admin/wisdom`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/wisdom/stats` | SuperAdmin | Global wisdom statistics (total tips, avg rating, views, shares, top categories, top rated tips). |
| GET | `/admin/wisdom/top` | SuperAdmin | Top rated wisdom tips. Query param: `limit` (default: `10`). |

## Integration Contracts

### Users Module

- **Profile update**: When a user views a wisdom tip, update `last_wisdom_id` on the user profile or `WisdomUserInteraction` model.
- **Authentication**: Uses `get_current_user` from `app.modules.wisdom.routes.dependencies` which decodes JWT and queries `User` from `app.modules.users.models`.
- **Admin access**: Uses `get_current_superadmin` which checks `user.role in ("superadmin", "admin")`.

### Notifications Module

- **Daily push notification**: `send_morning_notification_task` sends a push notification to announcement topics via `NotificationService` at 7:00 daily.
- **Topic**: Uses `FCM_TOPICS["announcements"]` from `app.modules.notifications.utils`, defaults to `"announcements"`.
- **Import**: Wrapped in try/except to handle cases where notifications module is unavailable.

### Core/LLM Integration

- **Wisdom generation**: `generate_wisdom_task` calls `WisdomService.generer_wisdom_du_jour()` which uses `LLMClient` from `app.modules.skills.utils.llm_client` to generate wisdom content via LLM.
- **Schedule**: Runs daily at 23:00 to generate the next day's wisdom tip.
- **Fallback**: If LLM generation fails or no tip exists, a static tip from `app.modules.wisdom.utils.static_catalog` is returned.

### Analytics

- **Rating recalculation**: `recalculate_ratings_task` calls `WisdomAnalyticsService.recalculer_tous_ratings()` at 5:00 daily to recalculate average ratings from user interactions.

## Celery Beat Schedule

| Task | Schedule | Description |
|------|----------|-------------|
| `generate_tomorrow_wisdom` | Daily 23:00 | Generate wisdom tip for tomorrow via LLM |
| `send_morning_notification` | Daily 7:00 | Send push notification to announcement topics |
| `recalculate_ratings` | Daily 5:00 | Recalculate average ratings for all tips |

## Database Models

- `WisdomTip` (`app.modules.wisdom.models.wisdom_tip`): Stores daily wisdom tips with content, category, ratings.
- `WisdomUserInteraction` (`app.modules.wisdom.models.wisdom_user_interaction`): Tracks user interactions (views, ratings, shares) with wisdom tips.

## Services

- `WisdomService` (`app.modules.wisdom.services.wisdom_service`): Core service for obtaining, generating, rating, and sharing wisdom tips.
- `WisdomAnalyticsService` (`app.modules.wisdom.services.wisdom_analytics_service`): Analytics service for global stats and top tips.

## Rate Limits

- `wisdom_rate_limiter`: 30 requests per 60 seconds (daily tip, rating endpoints).
- `share_rate_limiter`: 3 requests per 86400 seconds (1 day) (share endpoint).

## Setup

1. Register the wisdom router in `app/main.py`:
   ```python
   from app.modules.wisdom.router import router as wisdom_router
   app.include_router(wisdom_router, prefix="/api/v1")
   ```

2. Add Celery beat schedule to your Celery app configuration:
   ```python
   from app.modules.wisdom.jobs.crons import BEAT_SCHEDULE
   celery_app.conf.beat_schedule = BEAT_SCHEDULE
   ```
