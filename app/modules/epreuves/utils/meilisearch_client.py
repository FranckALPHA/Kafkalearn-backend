"""
utils/meilisearch_client.py
===========================
Client MeiliSearch avec fallback SQL et cache Redis.
"""
import json
import logging
from typing import Optional, List, Dict, Any

from redis import Redis

from app.core.config import MEILI_URL, MEILI_MASTER_KEY, REDIS_URL
from app.modules.epreuves.utils.constants import MATIERES, NIVEAUX, SERIES, REGIONS

logger = logging.getLogger(__name__)


class MeiliClient:
    """Client MeiliSearch pour la recherche textuelle rapide."""

    def __init__(self, redis_client: Redis = None):
        self.redis = redis_client or Redis.from_url(REDIS_URL, decode_responses=True, db=3)
        self.cache_ttl = 120
        try:
            import meilisearch
            self.client = meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)
            self.index = self.client.index("documents")
            self.available = True
        except Exception as e:
            logger.warning(f"MeiliSearch unavailable: {e}")
            self.available = False

    async def search(
        self, query: str, filters: Dict[str, Any],
        sort: List[str] = None, page: int = 1, limit: int = 20,
    ) -> Dict[str, Any]:
        """Recherche textuelle avec filtres."""
        if not self.available:
            return await self._sql_fallback(query, filters, page, limit)

        try:
            filter_str = self._build_filters(filters)
            result = self.index.search(query, {
                "filter": filter_str,
                "sort": sort or ["created_at:desc"],
                "page": page,
                "hitsPerPage": limit,
                "attributesToRetrieve": [
                    "id", "nom_affiche", "matiere", "niveau", "serie",
                    "annee", "region", "type_doc", "notion_principale",
                    "difficulte_estimee", "nb_vues", "is_validated",
                ],
            })
            return {
                "hits": result["hits"],
                "total": result.get("totalHits", 0),
                "page": result.get("page", page),
                "limit": result.get("hitsPerPage", limit),
                "moteur": "meilisearch",
            }
        except Exception as e:
            logger.warning(f"MeiliSearch failed, fallback SQL: {e}")
            return await self._sql_fallback(query, filters, page, limit)

    def _build_filters(self, filters: Dict[str, Any]) -> Optional[str]:
        """Construit la clause filter MeiliSearch."""
        conditions = []
        for field in ["matiere", "niveau", "serie", "region", "type_doc", "langue"]:
            if filters.get(field):
                conditions.append(f"{field} = '{filters[field]}'")
        if filters.get("annee"):
            conditions.append(f"annee = {filters['annee']}")
        if not filters.get("include_non_validated"):
            conditions.append("is_validated = true")
        return " AND ".join(conditions) if conditions else None

    async def _sql_fallback(self, query, filters, page, limit):
        """Fallback recherche SQL."""
        from sqlalchemy.orm import Session
        from app.core.database import SessionLocal
        from app.modules.epreuves.models import Document

        db = SessionLocal()
        try:
            q = db.query(Document).filter(Document.is_validated == True, Document.is_deleted == False)
            if query:
                q = q.filter(
                    (Document.nom_affiche.ilike(f"%{query}%")) |
                    (Document.texte_extrait.ilike(f"%{query}%"))
                )
            for field in ["matiere", "niveau", "serie", "region", "type_doc"]:
                if filters.get(field):
                    q = q.filter(getattr(Document, field) == filters[field])
            total = q.count()
            results = q.offset((page - 1) * limit).limit(limit).all()
            return {
                "hits": [d.serialize_list_item() for d in results],
                "total": total,
                "page": page,
                "limit": limit,
                "moteur": "sql_fallback",
            }
        finally:
            db.close()

    def get_available_filters(self) -> Dict[str, List[str]]:
        """Récupère les valeurs disponibles pour les filtres UI."""
        cache_key = "epreuves:filtres:v1"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        filters = {
            "matieres": MATIERES,
            "niveaux": NIVEAUX,
            "series": SERIES,
            "annees": list(range(2026, 2018, -1)),
            "regions": REGIONS,
            "types": ["epreuve", "lecon"],
            "langues": ["fr", "en"],
        }

        self.redis.setex(cache_key, self.cache_ttl, json.dumps(filters))
        return filters

    def invalidate_filters_cache(self):
        """Invalide le cache des filtres."""
        self.redis.delete("epreuves:filtres:v1")

    def index_document(self, doc_data: Dict[str, Any]):
        """Indexe un document dans MeiliSearch."""
        if not self.available:
            return
        try:
            self.index.add_documents([doc_data], primary_key="id")
        except Exception as e:
            logger.error(f"MeiliSearch index error: {e}")

    def delete_document(self, doc_id: int):
        """Supprime un document de l'index."""
        if not self.available:
            return
        try:
            self.index.delete_document(str(doc_id))
        except Exception as e:
            logger.error(f"MeiliSearch delete error: {e}")
