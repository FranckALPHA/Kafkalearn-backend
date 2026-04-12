"""
jobs/tasks.py
=============
Taches Celery asynchrones pour le module calendar.
"""
import logging
from datetime import datetime, timedelta, timezone

from app.modules.calendar.jobs.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def _get_db():
    """Cree une session DB dediee pour les taches Celery."""
    return SessionLocal()


# ─── Taches d'activite utilisateur ───────────────────────────────

@celery_app.task(name="calendar.tasks.log_user_activity", queue="default", bind=True, max_retries=3)
def log_user_activity_task(
    self,
    user_id: str,
    activity_type: str,
    item_id: int = None,
    item_name: str = None,
    matiere: str = None,
    duree_secondes: int = None,
    source_module: str = "calendar",
):
    """Cree un enregistrement UserActivity."""
    db = _get_db()
    try:
        from app.modules.users.models import UserActivity

        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            item_id=item_id,
            item_name=item_name,
            matiere=matiere,
            duree_secondes=duree_secondes,
            source_module=source_module,
        )
        db.add(activity)
        db.commit()
    except Exception as e:
        logger.error(f"Erreur log_user_activity user {user_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(name="calendar.tasks.update_user_study_stats", queue="default", bind=True, max_retries=3)
def update_user_study_stats_task(
    self,
    user_id: str,
    subject: str,
    accumulated_seconds: int,
    session_timestamp: str = None,
):
    """Met a jour User.total_heures_etude, total_sessions_etude et LearningProfile."""
    db = _get_db()
    try:
        from app.modules.users.models import User, UserLearningProfile

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User {user_id} introuvable pour update_study_stats")
            return

        user.total_sessions_etude = (user.total_sessions_etude or 0) + 1
        hours = accumulated_seconds / 3600.0
        user.total_heures_etude = round((user.total_heures_etude or 0.0) + hours, 2)

        # Mettre a jour le profil d'apprentissage
        profile = db.query(UserLearningProfile).filter(
            UserLearningProfile.user_id == user_id
        ).first()
        if profile:
            # Heures actives
            heures_actives = profile.heures_actives or {}
            if session_timestamp:
                ts = datetime.fromisoformat(session_timestamp)
                hour_key = str(ts.hour)
                heures_actives[hour_key] = heures_actives.get(hour_key, 0) + 1
            profile.heures_actives = heures_actives

            # Jours actifs
            jours_actifs = profile.jours_actifs or {}
            if session_timestamp:
                ts = datetime.fromisoformat(session_timestamp)
                day_key = ts.strftime("%A")
                jours_actifs[day_key] = jours_actifs.get(day_key, 0) + 1
            profile.jours_actifs = jours_actifs

            # Matieres frequentes
            matieres_frequentes = profile.matieres_frequentes or {}
            matieres_frequentes[subject] = matieres_frequentes.get(subject, 0) + 1
            profile.matieres_frequentes = matieres_frequentes

        db.commit()
    except Exception as e:
        logger.error(f"Erreur update_user_study_stats user {user_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


# ─── Taches de notification ──────────────────────────────────────

@celery_app.task(name="calendar.tasks.send_session_reminder", queue="default", bind=True, max_retries=2)
def send_session_reminder_task(
    self,
    user_id: str,
    session_id: int,
    subject: str,
    planned_start: str,
):
    """Envoie un rappel de session via NotificationService."""
    db = _get_db()
    try:
        from app.modules.notifications.services.notification_service import NotificationService

        service = NotificationService(db=db)
        service.send_to_user(
            user_id=user_id,
            title="Rappel de session",
            body=f"Votre session de {subject} commence dans 15 minutes.",
            type_notif="session_rappel",
            data={"session_id": session_id, "planned_start": planned_start},
        )
    except Exception as e:
        logger.error(f"Erreur send_session_reminder session {session_id} user {user_id}: {e}")
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()


@celery_app.task(name="calendar.tasks.notify_streak_milestone", queue="default", bind=True, max_retries=2)
def notify_streak_milestone_task(
    self,
    user_id: str,
    new_streak: int,
    milestones: list,
):
    """Envoie une notification de milestone de streak."""
    db = _get_db()
    try:
        from app.modules.notifications.services.notification_service import NotificationService

        milestone_str = ", ".join(str(m) for m in milestones)
        service = NotificationService(db=db)
        service.send_to_user(
            user_id=user_id,
            title=f"Streak atteint: {new_streak} jours!",
            body=f"Felicitations! Tu as atteint un streak de {new_streak} jours. Milestones: {milestone_str}",
            type_notif="streak_danger",
            data={"streak": new_streak, "milestones": milestones},
        )
    except Exception as e:
        logger.error(f"Erreur notify_streak_milestone user {user_id}: {e}")
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()


# ─── Taches de maintenance ───────────────────────────────────────

@celery_app.task(name="calendar.tasks.sync_expired_sessions", queue="cron", bind=True, max_retries=3)
def sync_expired_sessions_task(self):
    """Bulk update des sessions expirees vers le statut failed."""
    db = _get_db()
    try:
        from app.modules.calendar.models import CalendarSession
        from sqlalchemy import update as sa_update

        now = datetime.now(timezone.utc)

        # planned/active/paused → failed si planned_end + 10 min < now
        cutoff_failed = now - timedelta(minutes=10)
        result = db.execute(
            sa_update(CalendarSession)
            .where(
                CalendarSession.status.in_(["planned", "active", "paused"]),
                CalendarSession.planned_end < cutoff_failed,
            )
            .values(status="failed")
            .execution_options(synchronize_session=False)
        )

        # planned → skipped si planned_start + 2h < now et aucun ping
        cutoff_skipped = now - timedelta(hours=2)
        result_skipped = db.execute(
            sa_update(CalendarSession)
            .where(
                CalendarSession.status == "planned",
                CalendarSession.planned_start < cutoff_skipped,
                CalendarSession.last_ping.is_(None),
            )
            .values(status="skipped")
            .execution_options(synchronize_session=False)
        )

        db.commit()
        logger.info(
            f"Sync expired sessions: {result.rowcount} failed, {result_skipped.rowcount} skipped"
        )
    except Exception as e:
        logger.error(f"Erreur sync_expired_sessions: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


# ─── Taches de suggestions ───────────────────────────────────────

@celery_app.task(name="calendar.tasks.generate_daily_suggestions_batch", queue="default", bind=True, max_retries=2)
def generate_daily_suggestions_batch_task(self, batch_size: int = 50):
    """Pre-genere les suggestions quotidiennes pour les utilisateurs actifs."""
    db = _get_db()
    try:
        from app.modules.users.models import User
        from app.modules.calendar.services.content_suggestion_service import ContentSuggestionService

        today = datetime.now(timezone.utc)

        active_users = db.query(User).filter(
            User.is_active.is_(True),
            User.is_deleted.is_(False),
            User.derniere_activite_at >= today - timedelta(days=7),
        ).limit(batch_size).all()

        service = ContentSuggestionService(db=db)
        generated = 0
        for user in active_users:
            try:
                await_service = ContentSuggestionService(db=db)
                import asyncio
                asyncio.run(await_service.generer_suggestions_jour(str(user.id), today))
                generated += 1
            except Exception as e:
                logger.error(f"Erreur suggestions user {user.id}: {e}")
                continue

        logger.info(f"Generated daily suggestions for {generated}/{len(active_users)} users")
    except Exception as e:
        logger.error(f"Erreur generate_daily_suggestions_batch: {e}")
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()


# ─── Taches de rappels horaires ──────────────────────────────────

@celery_app.task(name="calendar.tasks.send_session_reminders_hourly", queue="cron", bind=True, max_retries=2)
def send_session_reminders_hourly_task(self):
    """Envoie des rappels pour les sessions commencant dans 15-20min."""
    db = _get_db()
    try:
        from app.modules.calendar.models import CalendarSession

        now = datetime.now(timezone.utc)
        window_start = now + timedelta(minutes=15)
        window_end = now + timedelta(minutes=20)

        upcoming_sessions = db.query(CalendarSession).filter(
            CalendarSession.status == "planned",
            CalendarSession.planned_start >= window_start,
            CalendarSession.planned_start <= window_end,
        ).all()

        for session in upcoming_sessions:
            try:
                send_session_reminder_task.delay(
                    user_id=str(session.user_id),
                    session_id=session.id,
                    subject=session.subject,
                    planned_start=session.planned_start.isoformat(),
                )
            except Exception as e:
                logger.error(f"Erreur enqueue reminder session {session.id}: {e}")
                continue

        logger.info(f"Queued {len(upcoming_sessions)} session reminders")
    except Exception as e:
        logger.error(f"Erreur send_session_reminders_hourly: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


# ─── Taches de performance hebdomadaire ──────────────────────────

@celery_app.task(name="calendar.tasks.calculate_weekly_performance", queue="cron", bind=True, max_retries=2)
def calculate_weekly_performance_task(self):
    """Calcule les stats de performance hebdomadaire pour les utilisateurs actifs."""
    db = _get_db()
    try:
        from app.modules.users.models import User
        from app.modules.calendar.services.performance_report_service import PerformanceReportService

        active_users = db.query(User).filter(
            User.is_active.is_(True),
            User.is_deleted.is_(False),
            User.derniere_activite_at >= datetime.now(timezone.utc) - timedelta(days=7),
        ).all()

        service = PerformanceReportService(db=db)
        calculated = 0
        for user in active_users:
            try:
                import asyncio
                asyncio.run(service.calculer_rapport(str(user.id), periode_jours=7))
                calculated += 1
            except Exception as e:
                logger.error(f"Erreur performance user {user.id}: {e}")
                continue

        logger.info(f"Calculated weekly performance for {calculated}/{len(active_users)} users")
    except Exception as e:
        logger.error(f"Erreur calculate_weekly_performance: {e}")
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()
