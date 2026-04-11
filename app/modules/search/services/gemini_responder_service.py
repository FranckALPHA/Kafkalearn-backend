"""
services/gemini_responder_service.py
====================================
Génération de réponses LLM à partir des chunks de recherche.
"""
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.search.services.base import SearchBaseService

logger = logging.getLogger(__name__)


class GeminiResponderService(SearchBaseService):
    """Génération de réponses IA basées sur les chunks RAG."""

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    async def generer_reponse(
        self,
        requete: str,
        chunks: List[Dict[str, Any]],
        mode: str = "reponse",
        langue: str = "fr",
        historique_session: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Génère une réponse IA à partir des chunks.

        Args:
            requete: Question de l'utilisateur
            chunks: Liste des chunks contextuels
            mode: "reponse", "resume", ou "exercices_similaires"
            langue: "fr" ou "en"
            historique_session: Historique conversationnel optionnel

        Returns:
            Dict avec texte, sources_citees, mode, confiance
        """
        try:
            # Construction du contexte
            contexte = self._construire_contexte(chunks)

            # Génération (placeholder - remplacer par appel LLM réel)
            reponse = self._generer_texte(requete, contexte, mode, langue)

            sources_citees = [c["chunk_id"] for c in chunks[:3] if c.get("chunk_id")]

            return {
                "texte": reponse,
                "sources_citees": sources_citees,
                "mode": mode,
                "confiance": 0.85,
            }
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            return {
                "texte": None,
                "erreur_code": "LLM_ERROR",
                "sources_citees": [],
                "mode": mode,
                "confiance": None,
            }

    def _construire_contexte(self, chunks: List[Dict[str, Any]]) -> str:
        """Construit le contexte RAG à partir des chunks."""
        parties = []
        for i, chunk in enumerate(chunks[:5], 1):
            doc_nom = chunk.get("document_nom", "Document inconnu")
            texte = chunk.get("texte_chunk", "")
            parties.append(f"[Source {i}: {doc_nom}]\n{texte}")
        return "\n\n---\n\n".join(parties)

    def _generer_texte(
        self, requete: str, contexte: str, mode: str, langue: str
    ) -> str:
        """
        Placeholder pour la génération LLM.
        TODO: Remplacer par appel réel à Gemini/Mistral/OpenRouter.
        """
        if mode == "reponse":
            return (
                f"Voici une réponse à votre question : « {requete} »\n\n"
                f"Basé sur les documents trouvés, voici les informations pertinentes :\n"
                f"{contexte[:500]}..."
            )
        elif mode == "resume":
            return f"Résumé des documents trouvés pour « {requete} » :\n\n{contexte[:300]}..."
        elif mode == "exercices_similaires":
            return f"Voici des exercices similaires à « {requete} » :\n\n1. Exercice type 1...\n2. Exercice type 2..."
        return f"Réponse à : {requete}"
