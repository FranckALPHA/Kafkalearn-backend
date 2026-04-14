"""
services/meilisearch_service.py
===============================
Recherche textuelle rapide via Meilisearch (endpoint /lite).
"""
import logging
from typing import Dict, Any, List, Optional

import meilisearch
from sqlalchemy.orm import Session

from app.modules.search.services.base import SearchBaseService
from app.core.config import MEILI_URL, MEILI_MASTER_KEY

logger = logging.getLogger(__name__)


class MeilisearchService(SearchBaseService):
    """
    Service de recherche textuelle via Meilisearch.
    Pour les recherches rapides sans IA ni vectorisation.
    """

    def __init__(self, db: Session, redis=None):
        super().__init__(db, redis)
        self.client = meilisearch.Client(MEILI_URL, MEILI_MASTER_KEY)
        self.index_name = "epreuves_textes"  # Index principal

    async def search(self, payload) -> Dict[str, Any]:
        """
        Recherche textuelle simple via Meilisearch.

        Args:
            payload: LiteSearchRequest avec q, matiere, niveau, limit

        Returns:
            Dict avec hits, total, et latence
        """
        import time
        start = time.time()

        # Construction des filtres
        filter_conditions = []
        if payload.matiere:
            filter_conditions.append(f"matiere = '{payload.matiere}'")
        if payload.niveau:
            filter_conditions.append(f"niveau = '{payload.niveau}'")

        # Recherche Meilisearch
        try:
            index = self.client.index(self.index_name)
            search_params = {
                "limit": payload.limit,
                "attributesToHighlight": ["titre", "contenu"],
                "highlightPreTag": "<mark>",
                "highlightPostTag": "</mark>",
            }

            if filter_conditions:
                search_params["filter"] = " AND ".join(filter_conditions)

            results = index.search(payload.q, search_params)

            latency_ms = int((time.time() - start) * 1000)

            return {
                "hits": self._format_hits(results.get("hits", [])),
                "total": results.get("estimatedTotalHits", 0),
                "latency_ms": latency_ms,
                "query": payload.q,
                "filters_applied": filter_conditions,
            }

        except meilisearch.errors.MeilisearchApiError as e:
            logger.error(f"Meilisearch API error: {e}")
            return {
                "hits": [],
                "total": 0,
                "latency_ms": -1,
                "error": "MEILISEARCH_ERROR",
                "query": payload.q,
            }
        except Exception as e:
            logger.error(f"Meilisearch error: {e}")
            return {
                "hits": [],
                "total": 0,
                "latency_ms": -1,
                "error": "SEARCH_ERROR",
                "query": payload.q,
            }

    def _format_hits(self, hits: List[Dict]) -> List[Dict]:
        """Formate les hits Meilisearch pour la réponse API."""
        formatted = []
        for hit in hits:
            formatted.append({
                "document_id": hit.get("document_id"),
                "titre": hit.get("titre", ""),
                "contenu": hit.get("contenu", "")[:500],  # Tronquer à 500 chars
                "matiere": hit.get("matiere"),
                "niveau": hit.get("niveau"),
                "annee": hit.get("annee"),
                "_formatted": hit.get("_formatted", {}),
            })
        return formatted

    def index_document(self, document: Dict[str, Any]) -> bool:
        """Indexe un document dans Meilisearch."""
        try:
            index = self.client.index(self.index_name)
            index.add_documents([document], primary_key="document_id")
            return True
        except Exception as e:
            logger.error(f"Failed to index document: {e}")
            return False

    def delete_document(self, document_id: str) -> bool:
        """Supprime un document de l'index."""
        try:
            index = self.client.index(self.index_name)
            index.delete_document(document_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    def reindex_all(self, documents: List[Dict[str, Any]]) -> bool:
        """Réindexe tous les documents (pour sync complète)."""
        try:
            index = self.client.index(self.index_name)
            index.delete_all_documents()
            index.add_documents(documents, primary_key="document_id")
            return True
        except Exception as e:
            logger.error(f"Failed to reindex all: {e}")
            return False
