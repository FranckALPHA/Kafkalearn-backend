"""
utils/vespa_client.py
=====================
Client HTTP asynchrone pour Vespa avec retry et timeout.
"""
import time
import logging
from typing import List, Dict, Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.modules.search.utils.constants import VESPA_FIELD_MAP

logger = logging.getLogger(__name__)


class VespaClient:
    """Client HTTP pour Vespa avec gestion robuste des erreurs."""

    def __init__(self, endpoint: str = "http://localhost:18080", timeout_seconds: float = 10.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self.client = httpx.AsyncClient(timeout=self.timeout)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    )
    async def hybrid_search(
        self,
        query_vector: List[float],
        query_text: str,
        filters: Dict[str, Any],
        top_k: int = 10,
        rrf_k: int = 60,
    ) -> Dict[str, Any]:
        """Recherche hybride ANN + BM25 sur Vespa."""
        where_clause = self._build_where_clause(filters)

        yql = f"""
            select * from sources *
            where ({where_clause})
            and (
                ({{"targetHits": {top_k * 2}, "approximate": "true"}}nearestNeighbor(chunk_embedding, query_vector))
                or
                weakAnd(default contains @query_text or titre contains @query_text)
            )
            limit {top_k * 2}
        """

        payload = {
            "yql": yql,
            "query_text": query_text,
            "input.query(query_vector)": query_vector,
            "ranking": "hybrid_rank",
            "timeout": "8s",
            "presentation.format": "json",
        }

        if rrf_k:
            payload["ranking.features.query(rrf_k)"] = rrf_k

        try:
            start_ms = time.time() * 1000
            response = await self.client.post(
                f"{self.endpoint}/search/",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            latency_ms = int(time.time() * 1000 - start_ms)
            response.raise_for_status()
            data = response.json()

            return {
                "chunks": self._parse_hits(data.get("root", {}).get("children", [])),
                "total_hits": data.get("root", {}).get("fields", {}).get("totalCount", 0),
                "latency_ms": latency_ms,
                "coverage": data.get("root", {}).get("coverage", {}),
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Vespa HTTP {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Vespa error: {e}", exc_info=True)
            raise

    def _build_where_clause(self, filters: Dict[str, Any]) -> str:
        """Construit la clause WHERE YQL."""
        conditions = []
        for key, value in filters.items():
            if value and key in VESPA_FIELD_MAP:
                safe_value = str(value).replace("'", "''")
                conditions.append(f"{VESPA_FIELD_MAP[key]} = '{safe_value}'")
        return " and ".join(conditions) if conditions else "true"

    def _parse_hits(self, hits: List[Dict]) -> List[Dict]:
        """Extrait les chunks pertinents depuis la réponse Vespa."""
        chunks = []
        for hit in hits:
            fields = hit.get("fields", {})
            ranking_features = fields.get("rankingFeatures", {})
            chunks.append({
                "chunk_id": fields.get("chunk_id"),
                "document_id": fields.get("document_id"),
                "document_nom": fields.get("document_nom", ""),
                "texte_chunk": fields.get("texte_chunk", ""),
                "matiere": fields.get("matiere"),
                "niveau": fields.get("niveau"),
                "score_ann": ranking_features.get("nearestNeighbor(chunk_embedding,query_vector)"),
                "score_bm25": fields.get("relevance"),
                "chunk_idx": fields.get("chunk_idx"),
            })
        return chunks

    async def close(self):
        await self.client.aclose()
