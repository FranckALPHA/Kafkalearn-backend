"""
services/school_engagement_service.py
=====================================
Service de calcul de l'engagement des membres d'une ecole.
"""
import logging
from datetime import datetime, timedelta

from redis import Redis
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.modules.school.models.school import School
from app.modules.school.models.school_member import SchoolMember
from app.modules.school.services.base import SchoolBaseService
from app.modules.users.models.user import User

logger = logging.getLogger(__name__)


class SchoolEngagementService(SchoolBaseService):
    """Service de calcul de l'engagement d'une ecole."""

    def calculer_engagement(self, school_id: str) -> dict:
        """Calcule les indicateurs d'engagement de l'ecole.

        Met a jour School.nb_eleves_actifs et School.score_engagement_moyen.
        Retourne un dict avec les donnees d'engagement.
        """
        cutoff_7j = datetime.utcnow() - timedelta(days=7)

        # Compter les membres actifs (7j)
        actifs_7j = (
            self.db.query(SchoolMember)
            .join(User, SchoolMember.user_id == User.id)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.is_active == True,  # noqa: E712
                User.derniere_activite_at >= cutoff_7j,
            )
            .count()
        )

        # Moyenne du score global
        avg_score_result = (
            self.db.query(sql_func.avg(User.score_global))
            .join(SchoolMember, SchoolMember.user_id == User.id)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.is_active == True,  # noqa: E712
            )
            .scalar()
        )
        avg_score = float(avg_score_result) if avg_score_result is not None else 0.0

        # Moyenne du streak
        avg_streak_result = (
            self.db.query(sql_func.avg(User.streak_jours))
            .join(SchoolMember, SchoolMember.user_id == User.id)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.is_active == True,  # noqa: E712
            )
            .scalar()
        )
        avg_streak = int(avg_streak_result) if avg_streak_result is not None else 0

        # Moyenne du taux de reussite aux quiz
        avg_quiz_result = (
            self.db.query(
                sql_func.avg(
                    User.nb_quiz_reussis
                    / sql_func.nullif(User.nb_quiz_reussis + User.nb_quiz_echoues, 0)
                )
            )
            .join(SchoolMember, SchoolMember.user_id == User.id)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.is_active == True,  # noqa: E712
            )
            .scalar()
        )
        avg_quiz_success = (
            float(avg_quiz_result) if avg_quiz_result is not None else 0.0
        )

        # Score d'engagement composite (0-100)
        score_engagement = round(
            min(
                100,
                (avg_score * 0.4)
                + (min(avg_streak, 30) / 30 * 100 * 0.3)
                + (avg_quiz_success * 100 * 0.3),
            ),
            2,
        )

        # Mettre a jour l'ecole
        school = self.db.query(School).filter(School.id == school_id).first()
        if school:
            school.nb_eleves_actifs = actifs_7j
            school.score_engagement_moyen = score_engagement
            self.db.commit()

        return {
            "nb_eleves_actifs_7j": actifs_7j,
            "avg_score_global": round(avg_score, 2),
            "avg_streak": avg_streak,
            "avg_quiz_success_rate": round(avg_quiz_success, 4),
            "score_engagement": score_engagement,
        }
