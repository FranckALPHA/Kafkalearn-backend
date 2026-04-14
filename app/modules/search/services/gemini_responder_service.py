"""
services/gemini_responder_service.py
====================================
Génération de réponses LLM à partir des chunks de recherche.
Entièrement bilingue FR/EN via app.core.utils.i18n.
"""
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.search.services.base import SearchBaseService
from app.core.utils.i18n import t, format_msg, SEARCH_RESPONDER_SYSTEM, SEARCH_RESPONDER_USER_TEMPLATE

logger = logging.getLogger(__name__)


class GeminiResponderService(SearchBaseService):
    """Génération de réponses IA basées sur les chunks RAG. Bilingue FR/EN."""

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
        Génère une réponse IA à partir des chunks. Bilingue FR/EN.
        """
        try:
            contexte = self._construire_contexte(chunks)
            reponse = await self._generer_texte(requete, contexte, mode, langue)
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

    async def _generer_texte(
        self, requete: str, contexte: str, mode: str, langue: str
    ) -> str:
        """
        Génère une réponse via LLMClient avec prompts bilingues.
        """
        try:
            from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
            from app.core.config import OPENROUTER_API_KEYS

            system_prompt = t(SEARCH_RESPONDER_SYSTEM, langue)
            user_prompt = format_msg(
                t(SEARCH_RESPONDER_USER_TEMPLATE, langue),
                query=requete,
                context=contexte,
            )

            api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
            llm = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)
            result = await llm.generate(
                messages=[{"role": "user", "content": user_prompt}],
                system_instruction=system_prompt,
                temperature=0.5,
                max_tokens=1000,
                response_format=None,
            )
            if result.get("text"):
                return result["text"]
        except Exception as e:
            logger.warning(f"LLM generation fallback: {e}")

        # Fallback statique bilingue
        return self._fallback_static(requete, contexte, mode, langue)

    def _fallback_static(self, requete: str, contexte: str, mode: str, langue: str) -> str:
        """Fallback statique bilingue."""
        if langue == "en":
            if mode == "reponse":
                return f"Here's an answer to: « {requete} »\n\nBased on the documents found:\n{contexte[:500]}..."
            elif mode == "resume":
                return f"Summary of documents for « {requete} »:\n\n{contexte[:300]}..."
            elif mode == "exercices_similaires":
                return f"Here are exercises similar to « {requete} »:\n\n1. Sample exercise 1...\n2. Sample exercise 2..."
            return f"Answer to: {requete}"
        else:
            if mode == "reponse":
                return f"Voici une réponse à votre question : « {requete} »\n\nBasé sur les documents trouvés :\n{contexte[:500]}..."
            elif mode == "resume":
                return f"Résumé des documents trouvés pour « {requete} » :\n\n{contexte[:300]}..."
            elif mode == "exercices_similaires":
                return f"Voici des exercices similaires à « {requete} » :\n\n1. Exercice type 1...\n2. Exercice type 2..."
            return f"Réponse à : {requete}"
