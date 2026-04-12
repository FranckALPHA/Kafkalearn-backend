import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session
from redis import Redis

from app.modules.calendar.services.base import CalendarBaseService
from app.modules.calendar.models import CalendarSession, SessionPingLog
from app.modules.calendar.utils.heartbeat_validator import HeartbeatValidator
from app.modules.calendar.utils.streak_calculator import StreakCalculator
from app.modules.calendar.utils.concentration_metrics import ConcentrationMetrics

logger = logging.getLogger(__name__)


class SessionStateService(CalendarBaseService):
    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)
        self.heartbeat_validator = (
            HeartbeatValidator(self.redis) if self.redis else None
        )

    # ─── Synchronisation des états ───────────────────────────────

    async def synchroniser_etats(self, user_id: str) -> None:
        now = datetime.now(timezone.utc)

        # active → paused si last_ping > 15 min
        cutoff_paused = now - timedelta(minutes=15)
        self.db.execute(
            update(CalendarSession)
            .where(
                CalendarSession.user_id == user_id,
                CalendarSession.status == "active",
                CalendarSession.last_ping < cutoff_paused,
            )
            .values(status="paused")
            .execution_options(synchronize_session=False)
        )

        # planned/active/paused → failed si planned_end + 10 min < now
        cutoff_failed = now - timedelta(minutes=10)
        self.db.execute(
            update(CalendarSession)
            .where(
                CalendarSession.user_id == user_id,
                CalendarSession.status.in_(["planned", "active", "paused"]),
                CalendarSession.planned_end < cutoff_failed,
            )
            .values(status="failed")
            .execution_options(synchronize_session=False)
        )

        # planned → skipped si planned_start + 2h < now et aucun ping
        cutoff_skipped = now - timedelta(hours=2)
        self.db.execute(
            update(CalendarSession)
            .where(
                CalendarSession.user_id == user_id,
                CalendarSession.status == "planned",
                CalendarSession.planned_start < cutoff_skipped,
                CalendarSession.last_ping.is_(None),
            )
            .values(status="skipped")
            .execution_options(synchronize_session=False)
        )

        self.db.commit()
        logger.info("Synchronisation des états de session terminée pour user %s", user_id)

    # ─── Traitement du ping ──────────────────────────────────────

    async def traiter_ping(
        self, session_id: int, user_id: str, elapsed_client: int = None
    ) -> dict:
        session = (
            self.db.query(CalendarSession)
            .with_for_update()
            .filter(CalendarSession.id == session_id)
            .first()
        )
        if not session:
            raise ValueError(f"Session {session_id} introuvable")

        if not self.heartbeat_validator:
            raise RuntimeError("HeartbeatValidator non disponible (redis manquante)")

        validation = await self.heartbeat_validator.validate_ping(
            session, user_id, elapsed_client
        )
        if not validation["allowed"]:
            raise PermissionError(f"Ping refusé: {validation['error']}")

        if validation.get("is_duplicate"):
            return session.serialize_detail()

        now = datetime.now(timezone.utc)
        delta = validation["delta_to_count"]

        # Transitions d'état
        if session.status == "planned":
            session.status = "active"
            session.actual_start = now

        if validation["is_pause_detected"]:
            session.nb_pauses = (session.nb_pauses or 0) + 1

        if delta > 0:
            session.accumulated_seconds = (session.accumulated_seconds or 0) + delta

        session.concentration_ratio = ConcentrationMetrics.calculate_concentration_ratio(
            session.accumulated_seconds or 0,
            session.planned_duration_minutes,
        )
        session.last_ping = now

        # Ping log
        ping_log = session.ping_log
        if ping_log is None:
            ping_log = SessionPingLog(session_id=session.id)
            self.db.add(ping_log)
        ping_log.add_ping(now, delta)

        self.db.commit()
        return session.serialize_detail()

    # ─── Complétion de session ───────────────────────────────────

    async def completer_session(
        self,
        session_id: int,
        user_id: str,
        humeur_fin: str = None,
        note_session: str = None,
    ) -> dict:
        session = (
            self.db.query(CalendarSession)
            .with_for_update()
            .filter(CalendarSession.id == session_id)
            .first()
        )
        if not session:
            raise ValueError(f"Session {session_id} introuvable")

        now = datetime.now(timezone.utc)
        session.status = "completed"
        session.actual_end = now
        session.humeur_fin = humeur_fin
        session.note_session = note_session
        session.concentration_ratio = ConcentrationMetrics.calculate_concentration_ratio(
            session.accumulated_seconds or 0,
            session.planned_duration_minutes,
        )

        self.db.commit()
        logger.info("Session %s complétée par user %s", session_id, user_id)

        # Pipeline post-complétion (non bloquant)
        try:
            await self.pipeline_post_completion(session)
        except Exception as e:
            logger.error("Erreur pipeline post-complétion: %s", e)

        return {
            "session_id": session.id,
            "status": session.status,
            "concentration_ratio": session.concentration_ratio,
            "accumulated_seconds": session.accumulated_seconds,
            "humeur_fin": session.humeur_fin,
        }

    # ─── Pipeline post-complétion ────────────────────────────────

    async def pipeline_post_completion(self, session: CalendarSession) -> None:
        user_id = str(session.user_id)

        try:
            from app.modules.users.jobs.tasks import (
                update_streak_task,
                recalc_score_task,
            )
        except ImportError:
            logger.warning("Tâches Celery users non disponibles")
            return

        try:
            # Log d'activité
            from app.modules.users.jobs.tasks import update_streak_task

            update_streak_task.delay(user_id)
        except Exception as e:
            logger.error("Erreur queue update_streak: %s", e)

        try:
            # Stats d'étude
            self._update_study_stats(session)
        except Exception as e:
            logger.error("Erreur update_study_stats: %s", e)

        try:
            # Recalcul du score
            recalc_score_task.delay(user_id)
        except Exception as e:
            logger.error("Erreur queue recalc_score: %s", e)

        try:
            # Vérification milestones streak
            self._check_streak_milestones(user_id)
        except Exception as e:
            logger.error("Erreur check_streak_milestones: %s", e)

    # ─── Helpers ─────────────────────────────────────────────────

    def _get_user_streak(self, user_id: str) -> int:
        from app.modules.users.models import User

        user = self.db.query(User).filter(User.id == user_id).first()
        return user.streak_jours if user else 0

    def _get_completed_sessions(self, user_id: str) -> list:
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        return (
            self.db.query(CalendarSession)
            .filter(
                CalendarSession.user_id == user_id,
                CalendarSession.status == "completed",
                CalendarSession.actual_end >= one_year_ago,
            )
            .order_by(CalendarSession.actual_end.desc())
            .all()
        )

    def _update_study_stats(self, session: CalendarSession) -> None:
        from app.modules.users.models import User

        user = self.db.query(User).filter(User.id == session.user_id).first()
        if not user:
            return

        user.total_sessions_etude = (user.total_sessions_etude or 0) + 1
        hours = (session.accumulated_seconds or 0) / 3600.0
        user.total_heures_etude = round((user.total_heures_etude or 0.0) + hours, 2)
        self.db.commit()

    def _check_streak_milestones(self, user_id: str) -> None:
        old_streak = self._get_user_streak(user_id)
        completed = self._get_completed_sessions(user_id)
        new_streak = StreakCalculator.calculate_current_streak(completed)
        milestones = StreakCalculator.check_milestone(old_streak, new_streak)

        if milestones:
            logger.info(
                "User %s a atteint les milestones streak: %s", user_id, milestones
            )
        if new_streak != old_streak:
            from app.modules.users.models import User

            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user.streak_jours = new_streak
                if new_streak > (user.streak_max or 0):
                    user.streak_max = new_streak
                self.db.commit()
