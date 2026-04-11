"""
services/reranker_service.py
============================
Reranking RRF (Reciprocal Rank Fusion) et filtrage.
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class RerankerService:
    """Service de reranking des résultats de recherche."""

    def reranker_rrf(
        self,
        chunks_ann: List[Dict[str, Any]],
        chunks_bm25: List[Dict[str, Any]],
        k: int = 60,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Fusion RRF des résultats ANN et BM25.
        Score RRF = Σ 1/(k + rang) pour chaque classement.
        """
        scores: Dict[int, float] = {}
        chunk_map: Dict[int, Dict[str, Any]] = {}

        # Scores ANN
        for rang, chunk in enumerate(
            sorted(chunks_ann, key=lambda c: c.get("score_ann") or 0, reverse=True), 1
        ):
            cid = chunk.get("chunk_id") or chunk.get("document_id")
            if cid is None:
                continue
            scores[cid] = scores.get(cid, 0) + 1 / (k + rang)
            chunk_map[cid] = chunk

        # Scores BM25
        for rang, chunk in enumerate(
            sorted(chunks_bm25, key=lambda c: c.get("score_bm25") or 0, reverse=True), 1
        ):
            cid = chunk.get("chunk_id") or chunk.get("document_id")
            if cid is None:
                continue
            scores[cid] = scores.get(cid, 0) + 1 / (k + rang)
            if cid not in chunk_map:
                chunk_map[cid] = chunk

        # Fusion et tri
        for cid, score in scores.items():
            if cid in chunk_map:
                chunk_map[cid]["score_rrf"] = round(score, 6)

        results = sorted(chunk_map.values(), key=lambda c: c.get("score_rrf") or 0, reverse=True)
        return results[:top_k]

    def filtrer_par_score(
        self, chunks: List[Dict[str, Any]], seuil: float = 0.01
    ) -> List[Dict[str, Any]]:
        """Filtre les chunks avec score_rrf < seuil."""
        return [c for c in chunks if (c.get("score_rrf") or 0) >= seuil]

    def enrichir_contexte(
        self, chunks: List[Dict[str, Any]], window: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Enrichit les chunks avec le contexte voisin.
        TODO: Implémenter avec accès à la DB pour récupérer chunk_idx ± window.
        """
        for chunk in chunks:
            chunk["contexte_enrichi"] = chunk.get("texte_chunk", "")
        return chunks
