# Calendar Module — Integration Guide

## Overview

The `calendar` module manages study sessions, timetables, personal study plans, and performance reports. It integrates with multiple other modules and external services.

---

## Endpoints

All endpoints are prefixed with `/calendar` and require authentication (JWT bearer token).

### Sessions (`/calendar`)

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| `GET` | `/calendar/sessions` | List sessions with filters (date_debut, date_fin, status, subject, pagination) | 60/min |
| `POST` | `/calendar/sessions` | Create a study session (201) | 10/min |
| `POST` | `/calendar/sessions/{session_id}/ping` | Send a heartbeat ping for an active session | 10/min per IP |
| `PATCH` | `/calendar/sessions/{session_id}/status` | Update session status (completed/failed/cancelled) | — |
| `GET` | `/calendar/suggestions` | Get study suggestions for a date | 30/min |
| `GET` | `/calendar/coach-insights` | Get personalized coach insights | — |
| `GET` | `/calendar/heatmap` | Get activity heatmap data (nb_jours query param, default 365, max 365) | — |

### Timetable (`/calendar/timetable`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/calendar/timetable/` | List timetable entries for user |
| `POST` | `/calendar/timetable/` | Create timetable entry |
| `DELETE` | `/calendar/timetable/{entry_id}` | Delete (deactivate) timetable entry |

### Personal Plan (`/calendar/personal-plan`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/calendar/personal-plan/` | List personal study entries |
| `POST` | `/calendar/personal-plan/` | Create personal study entry |
| `DELETE` | `/calendar/personal-plan/{entry_id}` | Delete (deactivate) personal study entry |

### Reports (`/calendar/reports`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/calendar/reports/performance` | Performance report (periode_jours query param, default 7) |
| `GET` | `/calendar/reports/weekly-summary` | Weekly overview: sessions count, total hours, streak |

---

## Cross-Module Contracts

### Users Module

| Integration | Details |
|-------------|---------|
| **Auth** | `get_current_user` from `app.modules.users.routes.dependencies` — JWT bearer token, returns `User` |
| **DB** | `get_db` from `app.modules.users.routes.dependencies` or local equivalent |
| **Rate Limiter** | `RateLimiter` and `get_rate_limiter_dependency` from `app.modules.users.utils.rate_limiter` |
| **LearningProfile** | `UserLearningProfile` — updated with `heures_actives`, `jours_actifs`, `matieres_frequentes` after session completion |
| **User Stats** | `User.total_heures_etude`, `User.total_sessions_etude` incremented after session completion |
| **Streak** | `User.streak_jours`, `User.streak_max` updated via `StreakService` after session completion |
| **Activity Logging** | `UserActivity` records created via `log_user_activity_task` for session events |
| **Score** | `recalc_score_task` from `app.modules.users.jobs.tasks` triggered after session completion |

### Memory Module

| Integration | Details |
|-------------|---------|
| **UserSectionProgress** | Queried for due sections (`next_review <= now`) to generate memory review suggestions |
| **MemorySection** | Joined with `UserSectionProgress` to filter by subject |

### Epreuves Module

| Integration | Details |
|-------------|---------|
| **DocumentService** | `Document` model queried for validated epreuves (`type_doc == "EPREUVE"`) ordered by `nb_vues` |
| **Search** | Documents filtered by subject (`matiere`) matching timetable/personal plan subjects |

### Notifications Module

| Integration | Details |
|-------------|---------|
| **Session Reminders** | `NotificationService.send_to_user()` sends `session_rappel` notifications 15-20 min before session start |
| **Streak Milestones** | `NotificationService.send_to_user()` sends `streak_danger` type notifications when streak milestones are reached |
| **Task Queue** | Celery tasks `send_session_reminder_task` and `notify_streak_milestone_task` enqueue notifications |

### Skills Module

| Integration | Details |
|-------------|---------|
| **SkillRecommenderService** | Referenced for skill-based suggestions (placeholder: generates "Exercice interactif" suggestions per subject) |

### Library Module

| Integration | Details |
|-------------|---------|
| **PedagogicalAsset** | Queried for recent personal assets (last 7 days) filtered by subject for suggestions |

---

## Celery Tasks

| Task Name | Queue | Description |
|-----------|-------|-------------|
| `calendar.tasks.log_user_activity` | default | Creates `UserActivity` record |
| `calendar.tasks.update_user_study_stats` | default | Updates user study stats and learning profile |
| `calendar.tasks.send_session_reminder` | default | Sends session reminder notification |
| `calendar.tasks.notify_streak_milestone` | default | Sends streak milestone notification |
| `calendar.tasks.sync_expired_sessions` | cron | Bulk updates expired sessions to failed/skipped (every 15 min) |
| `calendar.tasks.generate_daily_suggestions_batch` | default | Pre-generates daily suggestions for active users (daily at 6h) |
| `calendar.tasks.send_session_reminders_hourly` | cron | Sends reminders for sessions starting in 15-20 min (hourly) |
| `calendar.tasks.calculate_weekly_performance` | cron | Calculates weekly performance stats for active users (Sunday 5h) |

---

## Models

| Model | Table | Purpose |
|-------|-------|---------|
| `CalendarSession` | `calendar_sessions` | Study session lifecycle (planned → active → completed) |
| `CalendarTimetable` | `calendar_timetable` | Weekly timetable entries |
| `CalendarPersonalStudy` | `calendar_personal_study` | Personal study plan entries |
| `DailySuggestionsCache` | `daily_suggestions_cache` | Cached daily suggestions per user |
| `SessionPingLog` | `session_ping_logs` | Ping/heartbeat logs per session |

---

## Services

| Service | Purpose |
|---------|---------|
| `SessionStateService` | Session lifecycle: sync states, process pings, complete sessions, post-completion pipeline |
| `ContentSuggestionService` | Generate daily study suggestions from memory, epreuves, skills, and library |
| `StudyCoachService` | Generate personalized study insights based on user habits |
| `PerformanceReportService` | Calculate performance reports and heatmap data |

---

## Rate Limiters

| Limiter | Max Requests | Window | Used By |
|---------|-------------|--------|---------|
| `calendar_sessions_rate` | 60 | 60s | GET /sessions |
| `calendar_create_rate` | 10 | 60s | POST /sessions |
| `calendar_ping_rate` | 10 | 60s | POST /sessions/{id}/ping |
| `calendar_suggestions_rate` | 30 | 60s | GET /suggestions |
