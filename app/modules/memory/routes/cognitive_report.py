"""
routes/cognitive_report.py
==========================
Endpoint de rapport cognitif : vue d'ensemble du profil d'apprentissage
basée sur le graphe cognitif.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.modules.memory.routes.dependencies import (
    get_db,
    get_current_user,
    get_concept_graph_service,
    get_scheduler_service,
    get_stats_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory - Cognitive Report"])


@router.get("/cognitive-report")
async def get_cognitive_report(
    current_user: User = Depends(get_current_user),
    graph_service=Depends(get_concept_graph_service),
    scheduler_service=Depends(get_scheduler_service),
    stats_service=Depends(get_stats_service),
):
    """
    Rapport cognitif complet de l'utilisateur.

    Retourne :
    - lacunes : concepts où l'utilisateur a échoué, groupés par matière
    - maitrises : concepts maîtrisés avec score de confiance
    - parcours_recommande : chemin d'apprentissage optimal (prérequis + lacunes)
    - prochaines_revisions : sections dues pour révision (SM-2)
    - statistiques : compteurs globaux
    - matiere_principale : matière la plus travaillée
    """
    user_id = str(current_user.id)

    # Lacunes et maîtrises
    lacunes = graph_service.get_concepts_lacunes(user_id)
    maitrises = graph_service.get_concepts_maitrises(user_id)
    en_cours = graph_service.get_concepts_en_cours(user_id)

    # Parcours recommandé (basé sur la matière principale)
    stats = graph_service.get_statistiques_personnelles(user_id)
    matiere_principale = stats.get("matiere_principale")

    parcours_recommande = []
    if matiere_principale:
        # Pour chaque lacune dans la matière principale, calculer le parcours
        lacunes_matiere = lacunes.get(matiere_principale, [])
        for concept in lacunes_matiere[:3]:  # Max 3 concepts
            parcours = graph_service.get_parcours_recommande(user_id, concept, max_depth=8)
            parcours_recommande.extend(parcours)

        # Dédupliquer et limiter
        seen = set()
        parcours_unique = []
        for p in parcours_recommande:
            if p["concept"] not in seen:
                seen.add(p["concept"])
                parcours_unique.append(p)
        parcours_recommande = parcours_unique[:15]

    # Prochaines révisions (SM-2)
    sections_due = await scheduler_service.obtenir_sections_a_revoir(user_id)

    # Stats complètes (depuis MemoryStatsService)
    try:
        memory_stats = await stats_service.calculer_stats_utilisateur(user_id)
    except Exception as e:
        logger.warning(f"Could not compute memory stats: {e}")
        memory_stats = {}

    # Concepts déblocables (prochaine étape logique)
    deblocables = []
    if matiere_principale:
        deblocables = graph_service.get_concepts_debloques(user_id, matiere_principale)

    return {
        "user_id": user_id,
        "lacunes": lacunes,
        "maitrises": maitrises,
        "en_cours": en_cours,
        "parcours_recommande": parcours_recommande,
        "prochaines_revisions": [
            {
                "section_id": s["section"]["id"],
                "section_title": s["section"]["section_title"],
                "urgence": s["urgence"],
                "nb_jours_depuis": s["nb_jours_depuis_revision"],
            }
            for s in sections_due[:5]
        ],
        "statistiques": {
            "total_concepts": stats["total_concepts"],
            "nb_lacunes": stats["nb_lacunes"],
            "nb_maitrises": stats["nb_maitrises"],
            "matiere_principale": stats["matiere_principale"],
            "sections_engagees": memory_stats.get("total_sections", 0),
            "sections_completees": memory_stats.get("completed_sections", 0),
            "score_moyen": memory_stats.get("avg_score", 0),
            "precision": memory_stats.get("accuracy", 0),
        },
        "deblocables": deblocables[:5],
    }


@router.get("/cognitive-report/{concept}/prerequis")
async def get_concept_prerequis(
    concept: str,
    current_user: User = Depends(get_current_user),
    graph_service=Depends(get_concept_graph_service),
):
    """
    Retourne la chaîne de prérequis pour un concept donné.
    Utile pour répondre à : "Que dois-je réviser avant les intégrales ?"
    """
    user_id = str(current_user.id)
    prerequis = graph_service.get_pre_requis(concept, user_id, max_depth=10)

    return {
        "concept": concept,
        "prerequis": prerequis,
        "nb_prerequis": len(prerequis),
    }


@router.get("/cognitive-report/deblocables")
async def get_deblocables(
    matiere: str = None,
    current_user: User = Depends(get_current_user),
    graph_service=Depends(get_concept_graph_service),
):
    """
    Concepts que l'utilisateur peut maintenant aborder (tous prérequis maîtrisés).
    """
    user_id = str(current_user.id)
    deblocables = graph_service.get_concepts_debloques(user_id, matiere)

    return {
        "deblocables": deblocables,
        "nb_deblocables": len(deblocables),
    }
