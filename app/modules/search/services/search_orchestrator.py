"""
services/search_orchestrator.py
===============================
Orchestrateur du pipeline complet de recherche.
"""
import logging
import time
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import Session
from redis import Redis
from fastapi import HTTPException

from app.modules.search.services.base import SearchBaseService
from app.modules.search.services.retriever_service import RetrieverService
from app.modules.search.services.reranker_service import RerankerService
from app.modules.search.services.gemini_responder_service import GeminiResponderService
from app.modules.search.utils.quota_manager import QuotaManager
from app.modules.search.models import SearchLog, SearchChunkReturned
from app.modules.search.schemas.responses import (
    SearchResponse,
    ChunkResponse,
    IAReponse,
    QuotaRestant,
)

logger = logging.getLogger(__name__)


class SearchOrchestrator(SearchBaseService):
    """Orchestrateur du pipeline de recherche complet."""

    def __init__(self, db: Session, redis: Redis = None, vespa_endpoint: str = None):
        super().__init__(db, redis)
        self.retriever = RetrieverService(db, redis, vespa_endpoint)
        self.reranker = RerankerService()
        self.responder = GeminiResponderService(db, redis)
        self.quota_manager = QuotaManager(redis)

    async def rechercher(self, user, payload) -> SearchResponse:
        """
        Pipeline complet de recherche hybride avec réponse IA optionnelle.
        """
        start_total = time.time()

        # 1. Pré-vérifications
        texte = payload.texte.strip()
        if len(texte) < 3:
            raise HTTPException(status_code=400, detail="TEXTE_TROP_COURT")

        # 2. Vérification quota IA
        quota_consomme = False
        if payload.avec_ia and user:
            quota_ok = await self.quota_manager.check_and_consume(
                user_id=str(user.id), plan=user.plan_effectif
            )
            if not quota_ok:
                raise HTTPException(status_code=402, detail="QUOTA_DEPASSE")
            quota_consomme = True

        # 3. Recherche hybride
        retriever_result = await self.retriever.recherche_hybride(
            texte=texte,
            filtres=payload.to_filters_dict(),
            top_k=payload.top_k,
            poids_semantique=payload.poids_semantique,
            source_module="search",
        )

        if retriever_result.get("error"):
            return self._build_error_response(payload, retriever_result)

        chunks_bruts = retriever_result["chunks"]

        # 4. Reranking RRF
        chunks_ann = [c for c in chunks_bruts if c.get("score_ann")]
        chunks_rerankes = self.reranker.reranker_rrf(
            chunks_ann=chunks_ann, chunks_bm25=chunks_bruts, k=60, top_k=payload.top_k
        )

        chunks_finales = self.reranker.filtrer_par_score(chunks_rerankes, seuil=0.001)

        if payload.enrichir_contexte:
            chunks_finales = self.reranker.enrichir_contexte(chunks_finales, window=2)

        # 5. Génération réponse IA (optionnel)
        reponse_ia = None
        erreur_ia = None

        if payload.avec_ia and chunks_finales and user:
            try:
                reponse_ia_data = await self.responder.generer_reponse(
                    requete=texte,
                    chunks=chunks_finales,
                    mode=payload.mode_ia or "reponse",
                    langue=getattr(user, "langue", "fr") or "fr",
                    historique_session=[],
                )
                if reponse_ia_data.get("erreur_code"):
                    erreur_ia = reponse_ia_data["erreur_code"]
                else:
                    reponse_ia = IAReponse(**reponse_ia_data)
            except Exception as e:
                logger.error(f"LLM generation failed: {e}")
                erreur_ia = "LLM_ERROR"

        # 6. Construction réponse
        latence_totale = int((time.time() - start_total) * 1000)

        quota_restant = None
        if user:
            qr = await self.quota_manager.get_remaining(
                str(user.id), user.plan_effectif
            )
            quota_restant = QuotaRestant(**qr)

        response = SearchResponse(
            requete=texte,
            requete_normalisee=self._normaliser_texte(texte),
            intention_detectee=retriever_result.get("intention_detectee"),
            matiere_detectee=retriever_result.get("matiere_detectee"),
            nb_resultats=len(chunks_finales),
            chunks=[
                self._serialize_chunk(c, rang + 1)
                for rang, c in enumerate(chunks_finales)
            ],
            sources=self._extraire_sources(chunks_finales),
            reponse_ia=reponse_ia,
            erreur_ia=erreur_ia,
            quota_restant=quota_restant,
            latence_ms=latence_totale,
        )

        # 7. Logging en DB
        search_log = await self._creer_search_log(
            user=user,
            payload=payload,
            retriever_result=retriever_result,
            chunks_finales=chunks_finales,
            reponse_ia=reponse_ia,
            erreur_ia=erreur_ia,
            quota_consomme=quota_consomme,
            latence_totale=latence_totale,
        )
        response.search_log_id = search_log.id

        # 8. Background tasks (Celery - non bloquant)
        if user:
            try:
                from app.modules.search.jobs.tasks import enrich_profile_after_search_task
                enrich_profile_after_search_task.delay(
                    user_id=str(user.id),
                    requete=texte,
                    intention=retriever_result.get("intention_detectee"),
                    matiere=retriever_result.get("matiere_detectee"),
                    nb_resultats=len(chunks_finales),
                )
            except Exception as e:
                logger.warning(f"Failed to queue background task: {e}")

        return response

    async def _creer_search_log(self, **kwargs) -> SearchLog:
        """Crée l'entrée search_logs + chunks_retournes."""
        payload = kwargs["payload"]
        retriever = kwargs["retriever_result"]
        chunks = kwargs["chunks_finales"]

        log = SearchLog(
            user_id=kwargs["user"].id if kwargs["user"] else None,
            session_id=payload.session_id,
            texte_requete=payload.texte,
            texte_normalise=self._normaliser_texte(payload.texte),
            intention_detectee=retriever.get("intention_detectee"),
            methode_detection=retriever.get("methode_detection"),
            matiere_filtre=payload.matiere,
            matiere_detectee=retriever.get("matiere_detectee"),
            niveau_filtre=payload.niveau,
            serie_filtre=payload.serie,
            annee_filtre=payload.annee,
            type_doc_filtre=payload.type_doc,
            top_k_demande=payload.top_k,
            nb_chunks_retournes=len(chunks),
            nb_sources_distinctes=len(set(c.get("document_id") for c in chunks if c.get("document_id"))),
            reponse_ia_generee=kwargs["reponse_ia"] is not None,
            mode_ia=payload.mode_ia,
            erreur_ia=kwargs["erreur_ia"],
            quota_consomme=kwargs["quota_consomme"],
            score_semantique_max=retriever.get("score_semantique_max"),
            latence_vectorisation_ms=retriever.get("latence_vectorisation_ms"),
            latence_vespa_ms=retriever.get("latence_vespa_ms"),
            latence_totale_ms=kwargs["latence_totale"],
        )
        self.db.add(log)
        self.db.flush()

        # Chunks retournés
        for rang, chunk in enumerate(chunks, 1):
            chunk_log = SearchChunkReturned(
                search_log_id=log.id,
                chunk_id=chunk.get("chunk_id"),
                document_id=chunk.get("document_id"),
                rang_retourne=rang,
                score_ann=chunk.get("score_ann"),
                score_bm25=chunk.get("score_bm25"),
                score_rrf=chunk.get("score_rrf"),
                est_cite_dans_reponse=(
                    kwargs["reponse_ia"]
                    and chunk.get("chunk_id")
                    in (kwargs["reponse_ia"].sources_citees or [])
                ) if kwargs["reponse_ia"] else False,
            )
            self.db.add(chunk_log)

        self.db.commit()
        return log

    def _serialize_chunk(self, chunk: dict, rang: int) -> ChunkResponse:
        return ChunkResponse(
            chunk_id=chunk.get("chunk_id", 0),
            document_id=chunk.get("document_id", 0),
            document_nom=chunk.get("document_nom", ""),
            texte_chunk=chunk.get("texte_chunk", "")[:500],
            matiere=chunk.get("matiere"),
            niveau=chunk.get("niveau"),
            score_rrf=chunk.get("score_rrf"),
            rang=rang,
            est_cite=False,
        )

    def _extraire_sources(self, chunks: list) -> list:
        """Liste des sources uniques."""
        seen = set()
        sources = []
        for c in chunks:
            doc_id = c.get("document_id")
            doc_nom = c.get("document_nom", "")
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                sources.append({"document_id": doc_id, "nom": doc_nom})
        return sources

    def _build_error_response(self, payload, retriever_result) -> SearchResponse:
        return SearchResponse(
            requete=payload.texte,
            requete_normalisee=self._normaliser_texte(payload.texte),
            intention_detectee=retriever_result.get("intention_detectee"),
            matiere_detectee=None,
            nb_resultats=0,
            chunks=[],
            sources=[],
            erreur_ia=retriever_result.get("error"),
            latence_ms=retriever_result.get("latence_totale_ms", 0),
        )
