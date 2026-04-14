"""
services/asset_recommendation_service.py
=========================================
Service de recommandation d'assets pedagogiques.
"""
import json
import logging

from sqlalchemy import func, or_

from app.modules.library.models import PedagogicalAsset, AssetCopy

from .base import LibraryBaseService

logger = logging.getLogger(__name__)


class AssetRecommendationService(LibraryBaseService):
    # ─────────────────────────────────────────────────────────────
    # Recommander des assets
    # ─────────────────────────────────────────────────────────────
    async def recommander(self, user_id, limit: int = 10) -> list:
        """
        Genere des recommandations basees sur :
        - 40% : assets correspondant aux lacunes de l'utilisateur
        - 30% : assets populaires dans la classe/serie de l'utilisateur
        - 30% : assets recents bien notes
        """
        # Verifier le cache Redis
        cache_key = f"library:recommendations:{user_id}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Collecter les IDs a exclure (possedes + deja copies)
        excluded_ids = self._collect_excluded_ids(user_id)

        # Obtenir le profil utilisateur
        user_profile = self._get_user_profile(user_id)
        lacunes = user_profile.get("lacunes") or []
        classe = user_profile.get("classe")
        serie = user_profile.get("serie")

        recommendations = []

        # 1. Lacunes matching (40%)
        lacune_limit = max(1, int(limit * 0.4))
        if lacunes:
            lacune_assets = (
                self.db.query(PedagogicalAsset)
                .filter(
                    PedagogicalAsset.is_public == True,
                    PedagogicalAsset.is_deleted.isnot(True),
                    PedagogicalAsset.id.notin_(excluded_ids),
                    PedagogicalAsset.notion.in_(lacunes),
                )
                .order_by(PedagogicalAsset.note_moyenne.desc().nullslast())
                .limit(lacune_limit)
                .all()
            )
            for asset in lacune_assets:
                recommendations.append({
                    "asset": asset.serialize_list_item(mask_author=True),
                    "raison": f"Correspond a votre lacune : {asset.notion}",
                    "score_pertinence": 0.4,
                    "type_recommandation": "lacune",
                })

        # 2. Popular in user's classe/serie (30%)
        popular_limit = max(1, int(limit * 0.3))
        remaining = limit - len(recommendations)
        if remaining > 0 and classe:
            popular_query = self.db.query(PedagogicalAsset).filter(
                PedagogicalAsset.is_public == True,
                PedagogicalAsset.is_deleted.isnot(True),
                PedagogicalAsset.id.notin_(excluded_ids),
                PedagogicalAsset.class_name == classe,
            )
            if serie:
                popular_query = popular_query.filter(PedagogicalAsset.serie == serie)

            popular_assets = (
                popular_query.order_by(
                    func.coalesce(PedagogicalAsset.nb_vues, 0).desc()
                )
                .limit(popular_limit)
                .all()
            )
            for asset in popular_assets:
                if len(recommendations) >= limit:
                    break
                recommendations.append({
                    "asset": asset.serialize_list_item(mask_author=True),
                    "raison": f"Populaire en {classe}{f' {serie}' if serie else ''}",
                    "score_pertinence": 0.3,
                    "type_recommandation": "popular",
                })

        # 3. Recent well-rated (30%)
        remaining = limit - len(recommendations)
        if remaining > 0:
            from datetime import datetime, timedelta

            one_month_ago = datetime.utcnow() - timedelta(days=30)
            recent_assets = (
                self.db.query(PedagogicalAsset)
                .filter(
                    PedagogicalAsset.is_public == True,
                    PedagogicalAsset.is_deleted.isnot(True),
                    PedagogicalAsset.id.notin_(excluded_ids),
                    PedagogicalAsset.created_at >= one_month_ago,
                    PedagogicalAsset.note_moyenne.isnot(None),
                    PedagogicalAsset.note_moyenne >= 3.0,
                )
                .order_by(
                    PedagogicalAsset.note_moyenne.desc(),
                    PedagogicalAsset.created_at.desc(),
                )
                .limit(remaining)
                .all()
            )
            for asset in recent_assets:
                if len(recommendations) >= limit:
                    break
                recommendations.append({
                    "asset": asset.serialize_list_item(mask_author=True),
                    "raison": "Recent et bien note par la communaute",
                    "score_pertinence": 0.3,
                    "type_recommandation": "recent",
                })

        # Mettre en cache pour 1 heure
        self.redis.setex(cache_key, 3600, json.dumps(recommendations, default=str))

        return recommendations

    # ─────────────────────────────────────────────────────────────
    # Invalider le cache
    # ─────────────────────────────────────────────────────────────
    async def invalider_cache(self, user_id):
        """Supprime la cle de cache Redis pour un utilisateur."""
        cache_key = f"library:recommendations:{user_id}"
        self.redis.delete(cache_key)

    # ─────────────────────────────────────────────────────────────
    # Methodes internes
    # ─────────────────────────────────────────────────────────────
    def _collect_excluded_ids(self, user_id) -> list:
        """Collecte les IDs des assets possedes et deja copies par l'utilisateur."""
        owned = (
            self.db.query(PedagogicalAsset.id)
            .filter(PedagogicalAsset.user_id == user_id)
            .all()
        )
        owned_ids = [row[0] for row in owned]

        copied = (
            self.db.query(AssetCopy.copy_asset_id)
            .filter(AssetCopy.copied_by == user_id)
            .all()
        )
        copied_ids = [row[0] for row in copied]

        return list(set(owned_ids + copied_ids))

    def _get_user_profile(self, user_id) -> dict:
        """Recupere le profil de l'utilisateur (lacunes depuis le graphe, classe, serie)."""
        from app.modules.users.models import User
        from app.modules.memory.services.concept_graph_service import ConceptGraphService

        user = (
            self.db.query(User)
            .filter(User.id == user_id)
            .first()
        )
        if not user:
            return {}

        # Lacunes depuis le graphe cognitif (concept_graph)
        try:
            graph_svc = ConceptGraphService(self.db)
            lacunes_dict = graph_svc.get_concepts_lacunes(str(user_id))
            # Aplatir en liste de notions
            lacunes = []
            for notions in lacunes_dict.values():
                lacunes.extend(notions)
        except Exception:
            lacunes = []

        return {
            "lacunes": lacunes,
            "classe": user.classe,
            "serie": user.serie,
        }
