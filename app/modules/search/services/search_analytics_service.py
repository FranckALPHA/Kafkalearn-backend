"""
services/search_analytics_service.py
====================================
Métriques et analytics pour SuperAdmin.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.modules.search.services.base import SearchBaseService
from app.modules.search.models import SearchLog

logger = logging.getLogger(__name__)


class SearchAnalyticsService(SearchBaseService):
    """Analytics sur les recherches pour SuperAdmin."""

    def get_analytics(self, period: str = "7d") -> Dict[str, Any]:
        """Statistiques globales sur une période."""
        days = self._parse_period(period)
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(SearchLog).filter(SearchLog.created_at >= cutoff)

        total = query.count()
        with_ia = query.filter(SearchLog.reponse_ia_generee == True).count()  # noqa

        avg_latency = (
            self.db.query(func.avg(SearchLog.latence_totale_ms))
            .filter(SearchLog.created_at >= cutoff, SearchLog.latence_totale_ms.isnot(None))
            .scalar()
        ) or 0

        avg_chunks = (
            self.db.query(func.avg(SearchLog.nb_chunks_retournes))
            .filter(SearchLog.created_at >= cutoff)
            .scalar()
        ) or 0

        # Top matières
        top_matieres = (
            self.db.query(
                SearchLog.matiere_detectee,
                func.count(SearchLog.id).label("count"),
            )
            .filter(
                SearchLog.created_at >= cutoff,
                SearchLog.matiere_detectee.isnot(None),
            )
            .group_by(SearchLog.matiere_detectee)
            .order_by(desc("count"))
            .limit(10)
            .all()
        )

        # Top intentions
        top_intentions = (
            self.db.query(
                SearchLog.intention_detectee,
                func.count(SearchLog.id).label("count"),
            )
            .filter(
                SearchLog.created_at >= cutoff,
                SearchLog.intention_detectee.isnot(None),
            )
            .group_by(SearchLog.intention_detectee)
            .order_by(desc("count"))
            .all()
        )

        # Feedback distribution
        feedback_dist = (
            self.db.query(
                SearchLog.feedback_rating,
                func.count(SearchLog.id).label("count"),
            )
            .filter(
                SearchLog.created_at >= cutoff,
                SearchLog.feedback_rating.isnot(None),
            )
            .group_by(SearchLog.feedback_rating)
            .all()
        )

        return {
            "total_searches": total,
            "searches_with_ia": with_ia,
            "avg_latency_ms": round(float(avg_latency), 1),
            "avg_chunks_returned": round(float(avg_chunks), 1),
            "top_matieres": [{"matiere": m, "count": c} for m, c in top_matieres],
            "top_intentions": [{"intention": i, "count": c} for i, c in top_intentions],
            "feedback_distribution": {str(r): c for r, c in feedback_dist},
            "period": period,
        }

    def get_user_search_history(
        self, user_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Historique de recherche d'un utilisateur."""
        logs = (
            self.db.query(SearchLog)
            .filter(SearchLog.user_id == user_id)
            .order_by(SearchLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [log.serialize_minimal() for log in logs]

    def get_popular_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Requêtes les plus fréquentes."""
        results = (
            self.db.query(
                SearchLog.texte_requete,
                func.count(SearchLog.id).label("count"),
            )
            .filter(SearchLog.created_at >= datetime.utcnow() - timedelta(days=30))
            .group_by(SearchLog.texte_requete)
            .order_by(desc("count"))
            .limit(limit)
            .all()
        )
        return [{"query": q, "count": c} for q, c in results]

    def _parse_period(self, period: str) -> int:
        """Parse une période comme '7d', '30d', '90d'."""
        if period.endswith("d"):
            return int(period[:-1])
        if period.endswith("m"):
            return int(period[:-1]) * 30
        return 7
