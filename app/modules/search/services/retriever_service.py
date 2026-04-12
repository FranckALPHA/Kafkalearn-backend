"""
services/retriever_service.py
=============================
Recherche hybride ANN + BM25 via Vespa.
"""
import logging
import time
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.search.services.base import SearchBaseService
from app.modules.search.utils.vespa_client import VespaClient
from app.modules.search.utils.constants import (
    MOTS_INTENTION_EXPLICATION,
    MOTS_INTENTION_ENTRAINEMENT,
    MATIERES_MAPPING,
)

logger = logging.getLogger(__name__)


class RetrieverService(SearchBaseService):
    """Service de recherche hybride ANN + BM25."""

    def __init__(self, db: Session, redis: Redis = None, vespa_endpoint: str = None):
        super().__init__(db, redis)
        self.vespa = VespaClient(endpoint=vespa_endpoint or "http://localhost:18080")

    async def recherche_hybride(
        self,
        texte: str,
        filtres: Dict[str, Any],
        top_k: int = 10,
        poids_semantique: float = 0.7,
        source_module: str = "search",
    ) -> Dict[str, Any]:
        """Pipeline complet de recherche hybride."""
        start_total = time.time()

        # 1. Vectorisation (placeholder)
        start_vec = time.time()
        query_vector = self._vectoriser_texte(texte)
        latence_vectorisation = int((time.time() - start_vec) * 1000)

        # 2. Détection d'intention
        intention, methode = await self._detecter_intention(
            texte, filtres.get("matiere")
        )

        # Filtre implicite selon intention
        if intention == "explication" and not filtres.get("type_doc"):
            filtres["type_doc"] = "lecon"
        elif intention == "entrainement" and not filtres.get("type_doc"):
            filtres["type_doc"] = "epreuve"

        # 3. Recherche Vespa
        start_vespa = time.time()
        try:
            result = await self.vespa.hybrid_search(
                query_vector=query_vector,
                query_text=texte,
                filters=filtres,
                top_k=top_k * 2,
            )
            latence_vespa = int((time.time() - start_vespa) * 1000)
            chunks_bruts = result["chunks"]
        except Exception as e:
            logger.error(f"Vespa search failed: {e}")
            return {
                "chunks": [],
                "error": "VESPA_ERROR",
                "latence_vespa_ms": -1,
                "intention_detectee": intention,
                "methode_detection": methode,
            }

        # Détection matière
        matiere_detectee = self._detecter_matiere(texte)

        latence_totale = int((time.time() - start_total) * 1000)

        return {
            "chunks": chunks_bruts,
            "intention_detectee": intention,
            "methode_detection": methode,
            "matiere_detectee": matiere_detectee,
            "score_semantique_max": max(
                (c.get("score_ann") or 0) for c in chunks_bruts
            ) if chunks_bruts else None,
            "latence_vectorisation_ms": latence_vectorisation,
            "latence_vespa_ms": latence_vespa,
            "latence_totale_ms": latence_totale,
            "nb_chunks_bruts": len(chunks_bruts),
        }

    async def _detecter_intention(
        self, texte: str, matiere_contexte: str = None
    ) -> tuple:
        """Détecte l'intention: explication vs entrainement vs general."""
        texte_lower = texte.lower()

        if any(mot in texte_lower for mot in MOTS_INTENTION_EXPLICATION):
            return "explication", "regex"
        if any(mot in texte_lower for mot in MOTS_INTENTION_ENTRAINEMENT):
            return "entrainement", "regex"

        return "general", "fallback"

    def _detecter_matiere(self, texte: str) -> Optional[str]:
        """Détecte la matière depuis la requête."""
        texte_lower = texte.lower()
        for key, valeur in MATIERES_MAPPING.items():
            if key in texte_lower:
                return valeur
        return None

    def _vectoriser_texte(self, texte: str) -> List[float]:
        """
        Vectorisation du texte en embedding via FastEmbed si disponible.
        """
        try:
            from fastembed import TextEmbedding
            model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            embeddings = list(model.embed([texte]))
            return embeddings[0].tolist()
        except Exception:
            # Fallback: vecteur déterministe 768D
            import hashlib
            import random
            h = hashlib.sha256(texte.encode()).hexdigest()
            seed = int(h[:8], 16)
            rng = random.Random(seed)
            return [rng.gauss(0, 1) for _ in range(768)]
