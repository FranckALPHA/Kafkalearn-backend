"""
services/wisdom_analytics_service.py
=====================================
Service d'analytique pour le module wisdom.
"""
import logging

from sqlalchemy import func, desc

from app.modules.wisdom.services.base import WisdomBaseService
from app.modules.wisdom.models import WisdomTip, WisdomUserInteraction

logger = logging.getLogger(__name__)


class WisdomAnalyticsService(WisdomBaseService):
    """Service pour les statistiques et l'analytique des wisdom tips."""

    async def obtenir_stats_globales(self) -> dict:
        """Retourne les statistiques globales : total tips, avg rating, total views,
        total shares, top categories, top rated tips.
        """
        total_tips = self.db.query(func.count(WisdomTip.id)).scalar() or 0

        avg_rating_result = self.db.query(func.avg(WisdomTip.rating_moyen)).scalar()
        avg_rating = round(float(avg_rating_result), 2) if avg_rating_result else 0.0

        total_views = self.db.query(func.sum(WisdomTip.nb_vues)).scalar() or 0
        total_shares = self.db.query(func.sum(WisdomTip.nb_partages)).scalar() or 0

        # Top categories
        category_stats = (
            self.db.query(
                WisdomTip.category,
                func.count(WisdomTip.id).label("count"),
                func.avg(WisdomTip.rating_moyen).label("avg_rating"),
            )
            .group_by(WisdomTip.category)
            .order_by(desc("count"))
            .all()
        )

        top_categories = [
            {
                "category": row.category,
                "count": row.count,
                "avg_rating": round(float(row.avg_rating), 2) if row.avg_rating else None,
            }
            for row in category_stats
        ]

        # Top rated tips
        top_rated = (
            self.db.query(WisdomTip)
            .filter(WisdomTip.rating_moyen.isnot(None))
            .order_by(desc(WisdomTip.rating_moyen))
            .limit(5)
            .all()
        )

        top_rated_tips = [
            {
                "id": tip.id,
                "tip_date": str(tip.tip_date),
                "category": tip.category,
                "rating_moyen": tip.rating_moyen,
                "nb_notes": tip.nb_notes,
            }
            for tip in top_rated
        ]

        return {
            "total_tips": total_tips,
            "avg_rating": avg_rating,
            "total_views": total_views,
            "total_shares": total_shares,
            "top_categories": top_categories,
            "top_rated_tips": top_rated_tips,
        }

    async def recalculer_tous_ratings(self) -> int:
        """Recalcule le rating_moyen pour tous les tips qui ont des interactions avec notes.

        Retourne le nombre de tips mis a jour.
        """
        # Trouver tous les wisdom_id qui ont au moins une note
        tips_with_notes = (
            self.db.query(WisdomUserInteraction.wisdom_id)
            .filter(WisdomUserInteraction.note.isnot(None))
            .distinct()
            .all()
        )

        updated_count = 0
        for (wisdom_id,) in tips_with_notes:
            avg_result = (
                self.db.query(func.avg(WisdomUserInteraction.note))
                .filter(
                    WisdomUserInteraction.wisdom_id == wisdom_id,
                    WisdomUserInteraction.note.isnot(None),
                )
                .scalar()
            )

            nb_notes = (
                self.db.query(func.count(WisdomUserInteraction.id))
                .filter(
                    WisdomUserInteraction.wisdom_id == wisdom_id,
                    WisdomUserInteraction.note.isnot(None),
                )
                .scalar()
            )

            tip = self.db.query(WisdomTip).filter(WisdomTip.id == wisdom_id).first()
            if tip:
                tip.rating_moyen = round(float(avg_result), 2) if avg_result else None
                tip.nb_notes = nb_notes or 0
                updated_count += 1

        self.db.commit()
        logger.info("Recalcul ratings termine: %d tips mis a jour.", updated_count)
        return updated_count

    async def obtenir_top_citations(self, limit: int = 10) -> list:
        """Retourne les tips les mieux notes et les plus consultes.

        Classement combine : rating_moyen (prioritaire) puis nb_vues.
        """
        top_tips = (
            self.db.query(WisdomTip)
            .filter(WisdomTip.rating_moyen.isnot(None))
            .order_by(
                desc(WisdomTip.rating_moyen),
                desc(WisdomTip.nb_vues),
            )
            .limit(limit)
            .all()
        )

        return [
            {
                "id": tip.id,
                "tip_date": str(tip.tip_date),
                "content": tip.get_text(langue="fr"),
                "category": tip.category,
                "rating_moyen": tip.rating_moyen,
                "nb_vues": tip.nb_vues,
                "nb_partages": tip.nb_partages,
                "nb_notes": tip.nb_notes,
            }
            for tip in top_tips
        ]
