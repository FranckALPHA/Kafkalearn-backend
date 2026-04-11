"""
services/skill_analytics_service.py
===================================
Métriques et analytics pour SuperAdmin.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.modules.skills.services.base import SkillsBaseService
from app.modules.skills.models import SkillUsageLog, QuizSession, ChatSession

logger = logging.getLogger(__name__)


class SkillAnalyticsService(SkillsBaseService):
    """Analytics sur l'utilisation des skills pour SuperAdmin."""

    def get_analytics(self, period: str = "7d") -> Dict[str, Any]:
        """Statistiques globales sur une période."""
        days = self._parse_period(period)
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Usage par skill
        skills_usage = (
            self.db.query(
                SkillUsageLog.skill_type,
                func.count(SkillUsageLog.id).label("count"),
                func.avg(SkillUsageLog.latence_ms).label("avg_latency"),
                func.count(SkillUsageLog.id).filter(SkillUsageLog.succes == True).label("success_count"),  # noqa
            )
            .filter(SkillUsageLog.created_at >= cutoff)
            .group_by(SkillUsageLog.skill_type)
            .all()
        )

        # Quiz stats
        quiz_stats = (
            self.db.query(
                func.count(QuizSession.id).label("total"),
                func.avg(QuizSession.score_percent).label("avg_score"),
                func.count(QuizSession.id).filter(QuizSession.score_percent >= 50).label("passing"),
            )
            .filter(QuizSession.started_at >= cutoff)
            .first()
        )

        # Chat sessions
        chat_stats = (
            self.db.query(
                func.count(ChatSession.id).label("total"),
                func.avg(ChatSession.nb_messages).label("avg_messages"),
            )
            .filter(ChatSession.created_at >= cutoff)
            .first()
        )

        return {
            "period": period,
            "skills_usage": [
                {
                    "skill": s.skill_type,
                    "count": s.count,
                    "avg_latency_ms": round(float(s.avg_latency), 1) if s.avg_latency else 0,
                    "success_rate": round((s.success_count / s.count) * 100, 1) if s.count else 0,
                }
                for s in skills_usage
            ],
            "quiz_stats": {
                "total": quiz_stats.total if quiz_stats else 0,
                "avg_score": round(float(quiz_stats.avg_score), 1) if quiz_stats and quiz_stats.avg_score else 0,
                "passing_rate": round((quiz_stats.passing / quiz_stats.total) * 100, 1) if quiz_stats and quiz_stats.total else 0,
            },
            "chat_stats": {
                "total_sessions": chat_stats.total if chat_stats else 0,
                "avg_messages": round(float(chat_stats.avg_messages), 1) if chat_stats and chat_stats.avg_messages else 0,
            },
        }

    def get_top_skills(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Skills les plus utilisés."""
        results = (
            self.db.query(
                SkillUsageLog.skill_type,
                func.count(SkillUsageLog.id).label("count"),
            )
            .group_by(SkillUsageLog.skill_type)
            .order_by(desc("count"))
            .limit(limit)
            .all()
        )
        return [{"skill": r.skill_type, "count": r.count} for r in results]

    def get_top_matieres(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Matières les plus pratiquées."""
        results = (
            self.db.query(
                SkillUsageLog.matiere,
                func.count(SkillUsageLog.id).label("count"),
            )
            .filter(SkillUsageLog.matiere.isnot(None))
            .group_by(SkillUsageLog.matiere)
            .order_by(desc("count"))
            .limit(limit)
            .all()
        )
        return [{"matiere": r.matiere, "count": r.count} for r in results]

    def _parse_period(self, period: str) -> int:
        if period.endswith("d"):
            return int(period[:-1])
        if period.endswith("m"):
            return int(period[:-1]) * 30
        return 7
