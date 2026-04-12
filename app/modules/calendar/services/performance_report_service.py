import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from redis import Redis
from sqlalchemy import func, extract
from sqlalchemy.orm import Session

from app.modules.calendar.services.base import CalendarBaseService
from app.modules.calendar.models import CalendarSession

logger = logging.getLogger(__name__)


class PerformanceReportService(CalendarBaseService):
    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    # ─── Rapport de performance ──────────────────────────────────

    async def calculer_rapport(self, user_id: str, periode_jours: int = 7) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=periode_jours)

        sessions = (
            self.db.query(CalendarSession)
            .filter(
                CalendarSession.user_id == user_id,
                CalendarSession.status == "completed",
                CalendarSession.actual_end >= since,
            )
            .all()
        )

        total_sessions = len(sessions)
        total_heures = sum(s.accumulated_seconds or 0 for s in sessions) / 3600.0

        concentrations = [s.concentration_ratio for s in sessions if s.concentration_ratio is not None]
        avg_concentration = (
            sum(concentrations) / len(concentrations) if concentrations else 0.0
        )

        # Breakdown par matière
        subjects: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_seconds": 0})
        for s in sessions:
            if s.subject:
                subjects[s.subject]["count"] += 1
                subjects[s.subject]["total_seconds"] += s.accumulated_seconds or 0

        subjects_breakdown = {
            subject: {
                "count": data["count"],
                "total_hours": round(data["total_seconds"] / 3600.0, 2),
            }
            for subject, data in subjects.items()
        }

        # Streak
        streak = self._get_user_streak(user_id)

        # Distribution des humeurs
        mood_counts: dict[str, int] = defaultdict(int)
        for s in sessions:
            if s.humeur_fin:
                mood_counts[s.humeur_fin] += 1

        return {
            "periode_jours": periode_jours,
            "total_sessions": total_sessions,
            "total_heures_etude": round(total_heures, 2),
            "avg_concentration": round(avg_concentration, 3),
            "subjects_breakdown": subjects_breakdown,
            "streak": streak,
            "mood_distribution": dict(mood_counts),
        }

    # ─── Heatmap ─────────────────────────────────────────────────

    async def calculer_heatmap(self, user_id: str, nb_jours: int = 365) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=nb_jours)

        # Sessions complétées groupées par date
        results = (
            self.db.query(
                func.date(CalendarSession.actual_end).label("session_date"),
                func.count(CalendarSession.id).label("count"),
            )
            .filter(
                CalendarSession.user_id == user_id,
                CalendarSession.status == "completed",
                CalendarSession.actual_end >= since,
            )
            .group_by(func.date(CalendarSession.actual_end))
            .all()
        )

        data = []
        max_count = 0
        total = 0

        for row in results:
            date_str = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
            count = row[1]
            data.append({"date": date_str, "count": count})
            total += count
            if count > max_count:
                max_count = count

        return {
            "data": data,
            "total": total,
            "max_count": max_count,
        }

    # ─── Helpers ─────────────────────────────────────────────────

    def _get_user_streak(self, user_id: str) -> int:
        try:
            from app.modules.users.models import User

            user = self.db.query(User).filter(User.id == user_id).first()
            return user.streak_jours if user else 0
        except Exception:
            logger.warning("Impossible de récupérer le streak pour user %s", user_id)
            return 0
