# Notifications Module — Integration Guide

## Overview

The `notifications` module handles push notifications via Firebase Cloud Messaging (FCM),
user preferences, scheduled reminders, analytics, and admin broadcasting.

---

## Endpoints

### User endpoints (`/notifications`)

| Method | Path                     | Description                          | Auth    |
|--------|--------------------------|--------------------------------------|---------|
| GET    | `/notifications/me/history`          | Notification history (paginated)     | User    |
| PUT    | `/notifications/{id}/read`           | Mark notification as read            | User    |
| PUT    | `/notifications/read-all`            | Mark all as read                     | User    |
| GET    | `/notifications/me/preferences`      | Get notification preferences         | User    |
| PATCH  | `/notifications/me/preferences`      | Update notification preferences      | User    |
| POST   | `/notifications/register`            | Register/update device FCM token     | User    |

### Admin endpoints (`/admin/notifications`)

| Method | Path                            | Description                   | Auth        |
|--------|---------------------------------|-------------------------------|-------------|
| GET    | `/admin/notifications/stats`    | Notification statistics       | Admin only  |
| POST   | `/admin/notifications/send-topic` | Send to FCM topic             | Admin only  |
| GET    | `/admin/notifications/unread-counts` | Unread counts per user     | Admin only  |

---

## Integration Contracts

### Memory module (`app.modules.memory`)

When a section is due for review, call:

```python
from app.modules.notifications.services.notification_scheduler import NotificationScheduler

scheduler = NotificationScheduler(db=db, redis=redis)
scheduler.planifier_revision_memory(
    user_id=user_id,
    section_id=section_id,
    next_review_at=next_review_at,
    nb_sections=nb_sections,
)
```

### Calendar module

When a session is planned:

```python
scheduler.planifier_rappel_session(
    session_id=session_id,
    user_id=user_id,
    planned_start=planned_start,
    subject=subject,
)
```

When a session is cancelled:

```python
scheduler.annuler_rappel_session(session_id=session_id)
```

### Payment module

After a successful payment, send a confirmation notification:

```python
from app.modules.notifications.services.notification_service import NotificationService

svc = NotificationService(db=db)
svc.envoyer_template(
    user_id=user_id,
    template_type="payment_confirm",
    params={"plan": plan_name},
    type_notif="payment_confirm",
)
```

### Referral module

When a referred user becomes active:

```python
svc.envoyer_template(
    user_id=parrain_id,
    template_type="referral_actif",
    params={"prenom": prenom, "nb_restants": nb_restants},
    type_notif="referral_actif",
)
```

When the referral reward threshold is reached:

```python
svc.envoyer_template(
    user_id=parrain_id,
    template_type="referral_reward",
    params={"plan": plan_name},
    type_notif="referral_reward",
)
```

### Users module

The `derniere_activite_at` field on User should be updated on activity; the streak
danger task (`send_streak_danger_task`) reads this to find at-risk users.

---

## Models

| Model                    | Table                      | Description                        |
|--------------------------|----------------------------|------------------------------------|
| `Device`                 | `devices`                  | FCM tokens, platform, device info  |
| `NotificationLog`        | `notification_logs`        | Sent notification tracking         |
| `NotificationPreference` | `notification_preferences` | Per-user notification settings     |

---

## Scheduled Tasks (Celery Beat)

| Task                        | Frequency         | Description                    |
|-----------------------------|-------------------|--------------------------------|
| `send_quiz_morning_task`    | Daily 07:00       | Morning quiz reminders         |
| `send_memory_reminders_task`| Daily 07:30       | Memory review reminders        |
| `send_streak_danger_task`   | Daily 20:00       | Streak danger warnings         |
| `cleanup_invalid_tokens_task`| Weekly (Sun 04:00)| Deactivate invalid FCM tokens  |
| `cleanup_old_logs_task`     | Monthly (1st 05:00)| Delete logs older than 90 days |

> **Note:** The crontab schedules in `crons.py` are commented out; production should
> uncomment them and install `celery[schedule]`.

---

## Notification Types

| Type              | Description                     | Pref key         |
|-------------------|---------------------------------|------------------|
| `quiz_dispo`      | Quiz available                  | `quiz_dispo`     |
| `memory_review`   | Memory review reminder          | `memory_review`  |
| `session_rappel`  | Session reminder (15 min before)| `session_rappel` |
| `streak_danger`   | Streak at risk                  | `streaks`        |
| `payment_confirm` | Payment confirmation            | `payment`        |
| `lacune_detectee` | Learning gap detected           | `lacunes`        |
| `annonce`         | General announcement            | (always on)      |
| `referral_actif`  | Referred user active            | (always on)      |
| `referral_reward` | Referral bonus earned           | (always on)      |
