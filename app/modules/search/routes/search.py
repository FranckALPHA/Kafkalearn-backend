"""
routes/search.py
================
Endpoints principaux de recherche.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.modules.search.schemas.requests import (
    SearchRequest,
    FeedbackRequest,
    LiteSearchRequest,
)
from app.modules.search.schemas.responses import (
    SearchResponse,
    FeedbackResponse,
    SuggestionResponse,
)
from app.modules.search.routes.dependencies import (
    get_db,
    get_current_user,
    get_search_orchestrator,
    get_suggestion_service,
    get_rate_limiter_dependency,
    search_rate_limiter,
    search_lite_rate_limiter,
    suggestion_rate_limiter,
)
from app.modules.search.models import SearchLog
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


@router.post(
    "/rechercher",
    response_model=SearchResponse,
    dependencies=[Depends(get_rate_limiter_dependency(search_rate_limiter))],
    summary="Recherche hybride sémantique + lexicale",
    description="""
**Recherche hybride combinant recherche vectorielle (Vespa) et lexicale (Meilisearch).**

**Fonctionnement :**
1. Analyse l'intention de la requête (explication, entraînement, révision...)
2. Recherche vectorielle ANN via Vespa (similarité sémantique)
3. Recherche lexicale BM25 via Meilisearch (mots-clés exacts)
4. Fusion et reclassement des résultats (RRF)
5. Optionnel : génère une réponse IA basée sur les chunks trouvés

**Filtres disponibles :** `matiere`, `niveau`, `serie`, `annee`, `type_doc`

**Paramètres :**
- `texte` : la requête de recherche (min 3 caractères)
- `top_k` : nombre de résultats (1-50, défaut: 10)
- `avec_ia` : générer une réponse IA (défaut: false)
- `mode_ia` : type de réponse IA (`reponse`, `resume`, `exercices_similaires`)
- `poids_semantique` : poids de la recherche vectorielle vs lexicale (0.0-1.0, défaut: 0.7)

**Rate limit :** 10 requêtes/minute par utilisateur.
    """,
)
async def rechercher(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    orchestrator=Depends(get_search_orchestrator),
):
    """Hybrid search: vector + lexical + optional AI response."""
    return await orchestrator.rechercher(user=current_user, payload=payload)


@router.get(
    "/suggestions",
    response_model=SuggestionResponse,
    dependencies=[Depends(get_rate_limiter_dependency(suggestion_rate_limiter))],
    summary="Suggestions de recherche personnalisées",
    description="""
**Suggestions de recherche personnalisées basées sur le profil de l'utilisateur.**

**Ce que retourne l'endpoint :**
- Les 5 dernières recherches de l'utilisateur
- Les lacunes détectées (ex: "Révise derivees en Mathematiques")
- Les requêtes populaires globales pour compléter

**Les suggestions sont mises en cache 24h** — le cache est recalculé automatiquement.

**Rate limit :** 5 requêtes/minute.
    """,
)
async def get_suggestions(
    current_user: User = Depends(get_current_user),
    suggestion_service=Depends(get_suggestion_service),
):
    """Personalized search suggestions based on user profile and gaps."""
    return await suggestion_service.generer_suggestions(user_id=str(current_user.id))


@router.post("/{search_log_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    search_log_id: int,
    payload: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Enregistrement du feedback utilisateur sur une recherche.
    Utilisé pour l'amélioration continue des modèles.
    """
    log = db.query(SearchLog).filter(
        SearchLog.id == search_log_id,
        SearchLog.user_id == current_user.id,
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="SEARCH_NOT_FOUND")
    if log.feedback_rating is not None:
        raise HTTPException(status_code=409, detail="ALREADY_RATED")

    log.feedback_rating = payload.rating
    log.feedback_commentaire = payload.commentaire
    db.commit()

    return FeedbackResponse(
        message="Feedback enregistré. Merci !",
        search_log_id=search_log_id,
        rating=payload.rating,
    )


@router.delete("/historique", status_code=200)
async def delete_search_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Effacement de l'historique de recherche (conformité RGPD).
    """
    deleted_count = (
        db.query(SearchLog)
        .filter(SearchLog.user_id == current_user.id)
        .delete(synchronize_session=False)
    )

    # Vidage historique dans profil
    from app.modules.users.models import UserLearningProfile

    profile = (
        db.query(UserLearningProfile)
        .filter(UserLearningProfile.user_id == current_user.id)
        .first()
    )
    if profile:
        profile.historique_recherches = []

    db.commit()

    return {
        "message": "Historique de recherche supprimé.",
        "nb_entrees_supprimees": deleted_count,
    }


@router.post(
    "/lite",
    dependencies=[Depends(get_rate_limiter_dependency(search_lite_rate_limiter))],
)
async def recherche_lite(
    payload: LiteSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Recherche textuelle rapide via Meilisearch (sans IA, sans vectorisation).
    Pour les cas d'usage simples ou les connexions lentes.
    Rate limited: 20 req/min.
    """
    from app.modules.search.services.meilisearch_service import MeilisearchService
    service = MeilisearchService(db=db)
    return await service.search(payload)


@router.get("/historique")
async def get_search_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Historique de recherche de l'utilisateur."""
    logs = (
        db.query(SearchLog)
        .filter(SearchLog.user_id == current_user.id)
        .order_by(SearchLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return {"history": [log.serialize_minimal() for log in logs], "total": len(logs)}
