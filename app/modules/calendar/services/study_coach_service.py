import logging
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.calendar.services.base import CalendarBaseService
from app.modules.calendar.models import CalendarSession

logger = logging.getLogger(__name__)


class StudyCoachService(CalendarBaseService):
    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    async def generer_insights(self, user_id: str) -> list:
        """Analyse les habitudes d'étude et retourne 3 insights personnalisés."""
        insights = []

        # Données de base: sessions complétées des 30 derniers jours
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        sessions = (
            self.db.query(CalendarSession)
            .filter(
                CalendarSession.user_id == user_id,
                CalendarSession.status == "completed",
                CalendarSession.actual_end >= thirty_days_ago,
            )
            .all()
        )

        if not sessions:
            return [
                {
                    "type": "motivation",
                    "message": "Commence ta première session et je personnaliserai des conseils pour toi !",
                    "priority": 10,
                }
            ]

        # Insight 1: Pattern temporel (matin vs soir)
        morning_count = sum(
            1 for s in sessions if s.planned_start and s.planned_start.hour < 12
        )
        evening_count = sum(
            1 for s in sessions if s.planned_start and s.planned_start.hour >= 18
        )
        total = len(sessions)

        if morning_count > evening_count * 1.5:
            insights.append({
                "type": "time_pattern",
                "message": "Tu étudies plus le matin que le soir — c'est excellent pour la mémorisation !",
                "priority": 8,
                "data": {"morning_ratio": round(morning_count / total, 2)},
            })
        elif evening_count > morning_count * 1.5:
            insights.append({
                "type": "time_pattern",
                "message": "Tu es plutôt du soir — pense à bien dormir après tes sessions pour consolider.",
                "priority": 8,
                "data": {"evening_ratio": round(evening_count / total, 2)},
            })
        else:
            insights.append({
                "type": "time_pattern",
                "message": "Tu étudies à des heures variées — essaie de régulariser tes horaires pour de meilleurs résultats.",
                "priority": 6,
            })

        # Insight 2: Matière la plus régulière
        subject_counts: dict[str, int] = {}
        for s in sessions:
            if s.subject:
                subject_counts[s.subject] = subject_counts.get(s.subject, 0) + 1

        if subject_counts:
            top_subject = max(subject_counts, key=subject_counts.get)
            top_count = subject_counts[top_subject]
            insights.append({
                "type": "subject_regularity",
                "message": f"Les {top_subject.lower()} sont ta matière la plus régulière ({top_count} sessions ce mois).",
                "priority": 7,
                "data": {"subject": top_subject, "count": top_count},
            })

        # Insight 3: Concentration et fréquence
        avg_concentration = (
            sum(s.concentration_ratio for s in sessions if s.concentration_ratio is not None)
            / max(1, sum(1 for s in sessions if s.concentration_ratio is not None))
        )

        # Durée moyenne des sessions
        avg_duration = sum(s.accumulated_seconds or 0 for s in sessions) / max(1, total) / 60

        if avg_duration < 20 and total < 10:
            insights.append({
                "type": "frequency",
                "message": "Essaie des sessions plus courtes mais plus fréquentes — 20 min par jour valent mieux que 2h le weekend.",
                "priority": 9,
                "data": {"avg_duration_minutes": round(avg_duration, 1)},
            })
        elif avg_concentration < 0.5:
            insights.append({
                "type": "concentration",
                "message": "Ton ratio de concentration peut être amélioré. Essaie de réduire les distractions pendant tes sessions.",
                "priority": 9,
                "data": {"avg_concentration": round(avg_concentration, 2)},
            })
        else:
            insights.append({
                "type": "encouragement",
                "message": f"Continue comme ça ! Tu as fait {total} sessions ce mois avec une concentration moyenne de {round(avg_concentration * 100)}%.",
                "priority": 5,
                "data": {"total_sessions": total, "avg_concentration": round(avg_concentration, 2)},
            })

        # Tri par priorité et retour des 3 meilleurs
        insights.sort(key=lambda x: x["priority"], reverse=True)
        return insights[:3]
