# Daily Quiz Module — Integration Guide

## Overview

The `daily_quiz` module manages daily quiz generation, submission, correction, leaderboard tracking,
and streak monitoring for the Kafkalearn platform.

---

## Endpoints

### Quiz endpoints (`/daily-quiz`)

| Method | Path                                | Description                                      | Auth     |
|--------|-------------------------------------|--------------------------------------------------|----------|
| GET    | `/daily-quiz/today`                 | Get today's quiz (with/without answers)           | User     |
| POST   | `/daily-quiz/today/submit`          | Submit answers for today's quiz                   | User     |
| GET    | `/daily-quiz/stats`                 | Get user's quiz stats (participation, avg, streak)| User     |

### Leaderboard endpoints (`/daily-quiz/leaderboard`)

| Method | Path                                | Description                                      | Auth     |
|--------|-------------------------------------|--------------------------------------------------|----------|
| GET    | `/daily-quiz/leaderboard/`          | Get monthly leaderboard with user rank            | User     |

### Admin endpoints (`/admin/daily-quiz`)

| Method | Path                                | Description                                      | Auth        |
|--------|-------------------------------------|--------------------------------------------------|-------------|
| GET    | `/admin/daily-quiz/stats`           | Global quiz statistics                            | SuperAdmin  |
| POST   | `/admin/daily-quiz/generate/{date}` | Force quiz generation for a specific date         | SuperAdmin  |

---

## Integration Contracts

### Users module (`app.modules.users`)

- **Activity logging**: After a quiz submission, the users module should update the user's
  `derniere_activite_at` field to maintain streak accuracy.
- **Streak tracking**: The `QuizStreakService` reads `DailyQuizAttempt` records to calculate
  consecutive-day streaks. The users module can call `QuizStreakService.get_streak_info(user_id)`
  to display streak data on user profiles.

```python
from app.modules.daily_quiz.services.quiz_streak_service import QuizStreakService

streak_svc = QuizStreakService(db, redis)
info = await streak_svc.get_streak_info(user_id)
# info: {"current_streak": int, "longest_streak": int, "last_attempt_date": str}
```

### Notifications module (`app.modules.notifications`)

- **Quiz availability push**: The `notify_quiz_available_task` sends notifications to
  `quiz_dispo_fr` and `quiz_dispo_en` FCM topics each morning at 08:00.
- **Streak milestones**: When a user hits a streak milestone (3, 7, 14, 30, 100 days),
  the notification task sends a personalized push to that user.

```python
from app.modules.notifications.services.notification_service import NotificationService

svc = NotificationService(db=db)
svc.send_to_topic(
    topic="quiz_dispo_fr",
    title="Quiz du jour disponible!",
    body="Testez vos connaissances avec le quiz du jour.",
    type_notif="quiz_dispo",
)
```

### Calendar module (`app.modules.calendar`)

- **Quiz suggestion in daily plan**: The calendar module can call the daily quiz endpoint
  to embed today's quiz in the user's daily learning plan.

```python
from app.modules.daily_quiz.models import DailyQuiz

quiz = db.query(DailyQuiz).filter(DailyQuiz.quiz_date == date.today()).first()
if quiz:
    # Add to daily plan as a suggested activity
    plan_item = {
        "type": "daily_quiz",
        "quiz_id": quiz.id,
        "theme": quiz.theme,
        "estimated_duration_min": 10,
    }
```

---

## Models

| Model                  | Table                    | Description                          |
|------------------------|--------------------------|--------------------------------------|
| `DailyQuiz`            | `daily_quiz`             | Daily quiz definitions with questions|
| `DailyQuizAttempt`     | `daily_quiz_attempts`    | User quiz submissions and scores     |
| `MonthlyLeaderboard`   | `monthly_leaderboard`    | Monthly aggregated scores and ranks  |

---

## Scheduled Tasks (Celery Beat)

| Task                           | Frequency      | Description                           |
|--------------------------------|----------------|---------------------------------------|
| `generate_tomorrow_quiz_task`  | Daily 22:00    | Generate quiz for tomorrow            |
| `notify_quiz_available_task`   | Daily 08:00    | Push notifications for new quiz       |
| `calculate_monthly_ranks_task` | Daily 23:30    | Calculate and set leaderboard ranks   |

> **Note:** The schedules in `crons.py` use seconds for development. Production should
> uncomment crontab schedules: `crontab(hour=22, minute=0)`, etc.

---

## Response Schemas

### QuizResponse

```json
{
  "quiz": { "id": 1, "quiz_date": "2026-04-12", "questions": [...], "theme": "maths" },
  "deja_tente": false,
  "ma_tentative": null,
  "temps_restant_secondes": 43200
}
```

### SubmitResultResponse

```json
{
  "score": 4,
  "score_pourcentage": 80.0,
  "correction": [
    { "question_index": 0, "user_answer": "A", "correct_answer": "A", "is_correct": true, "explication": "..." }
  ],
  "streak": 5,
  "message_coaching": "Tres bon resultat!"
}
```

### LeaderboardResponse

```json
{
  "month_year": "2026-04",
  "top_entries": [
    { "user_prenom": "Ali***", "total_score": 950, "nb_participations": 10, "rang": 1 }
  ],
  "mon_rang": { "rang": 5, "total_score": 750, "nb_participations": 8 },
  "total_participants": 120
}
```
