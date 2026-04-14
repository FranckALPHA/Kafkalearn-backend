"""
routes/skills.py
================
Endpoints principaux pour l'exécution des skills IA.

**Skills disponibles :**
- `fiche` : Génère une fiche de révision structurée (PDF possible)
- `quiz` : Génère un quiz interactif avec correction
- `solver` : Résout un exercice étape par étape
- `corrige` : Corrige la copie d'un élève
- `tuteur` : Discussion libre avec un tuteur IA
- `visualisation` : Génère un graphe/diagramme mathématique

**Détection automatique** : si `skill` n'est pas précisé, l'IA détecte l'intention
depuis le prompt (ex: "explique les dérivées" → tuteur, "quiz sur les intégrales" → quiz).
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.modules.skills.schemas.requests import (
    SkillRunRequest,
    QuizSubmitRequest,
    DetectIntentRequest,
)
from app.modules.skills.schemas.responses import (
    SkillResultResponse,
    QuizCorrectionResponse,
    SkillListResponse,
    IntentDetectionResponse,
)
from app.modules.skills.routes.dependencies import (
    get_db,
    get_current_user,
    get_rate_limiter_dependency,
    skills_run_rate_limiter,
    skills_list_rate_limiter,
    skills_detect_rate_limiter,
    get_skill_dispatcher,
    get_idempotency_service,
    get_quiz_correction_service,
)
from app.modules.skills.models import QuizSession
from app.modules.users.models import User
from app.modules.skills.utils.constants import SKILL_CATALOG, PLAN_HIERARCHY, PLAN_REQUIREMENTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["Skills"])


def _is_plan_sufficient(user_plan: str, required_plan: str) -> bool:
    """Vérifie si le plan utilisateur est suffisant."""
    user_level = PLAN_HIERARCHY.index(user_plan) if user_plan in PLAN_HIERARCHY else 0
    required_level = PLAN_HIERARCHY.index(required_plan) if required_plan in PLAN_HIERARCHY else 0
    return user_level >= required_level


@router.post(
    "/run",
    response_model=SkillResultResponse,
    dependencies=[Depends(get_rate_limiter_dependency(skills_run_rate_limiter))],
    summary="Exécuter un skill IA",
    description="""
**Point d'entrée principal pour exécuter un skill IA.**

**Skills disponibles :**
- `fiche` : Fiche de révision structurée (définitions, formules, exemples)
- `quiz` : Quiz interactif avec questions progressives et correction
- `solver` : Résolution d'exercice étape par étape
- `corrige` : Correction de copie d'élève avec feedback
- `tuteur` : Discussion libre pour expliquer un concept
- `visualisation` : Graphe/diagramme mathématique

**Détection automatique** : si `skill` n'est pas précisé, l'IA détecte l'intention depuis le prompt.

**Exemple de requête :**
```json
{
  "skill": "quiz",
  "prompt": "quiz sur les dérivées en Maths Terminale C",
  "params": { "matiere": "Mathematiques", "niveau": "Tle", "nb_questions": 5 },
  "langue": "fr",
  "avec_rag": true
}
```

**Rate limit :** 10 requêtes/minute par utilisateur.
    """,
)
async def run_skill(
    payload: SkillRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    dispatcher=Depends(get_skill_dispatcher),
    idempotency=Depends(get_idempotency_service),
):
    """Run a skill: fiche, quiz, solver, corrige, tuteur, or visualisation."""
    # 1. Vérification idempotency
    idempotency_key = idempotency.generer_key_auto(
        user_id=str(current_user.id),
        prompt=payload.prompt,
        skill_type=payload.skill or "auto",
    )

    is_duplicate, previous_result = await idempotency.verifier_et_reserver(
        key=idempotency_key,
        ttl_seconds=60,
    )

    if is_duplicate and previous_result:
        raise HTTPException(
            status_code=409,
            detail="IDEMPOTENCY_DUPLICATE",
            headers={"X-Original-Request-Id": idempotency_key},
        )

    try:
        # 2. Dispatch vers le bon skill
        skill_instance, skill_type, detection_method = await dispatcher.dispatch(
            prompt=payload.prompt,
            skill_explicite=payload.skill,
            user_params=payload.params,
            user_plan=current_user.plan_effectif,
        )

        # 3. Exécution du skill
        from app.modules.skills.services.base_skill import SkillRequest

        skill_request = SkillRequest(
            user_id=str(current_user.id),
            prompt=payload.prompt,
            chat_session_id=payload.chat_session_id,
            langue=payload.langue or getattr(current_user, "langue", "fr") or "fr",
            params=payload.params,
            avec_rag=payload.avec_rag,
            user_document_id=payload.user_document_id,
            historique_session=[],
        )

        result = await skill_instance.run(skill_request)

        # 4. Persistences et background tasks
        from app.modules.skills.services.chat_service import ChatService

        chat_service = ChatService(db)

        if payload.chat_session_id:
            session_id = payload.chat_session_id
        else:
            session = await chat_service.creer_session(
                user_id=str(current_user.id),
                titre=payload.prompt[:50],
                matiere=payload.params.get("matiere"),
            )
            session_id = str(session.id)

        await chat_service.ajouter_message_pair(
            session_id=session_id,
            user_content=payload.prompt,
            assistant_result=result,
            skill_type=skill_type,
            matiere=payload.params.get("matiere"),
        )

        await idempotency.marquer_complete(idempotency_key, result.model_dump())

        # Background: enrichissement profil + extraction concepts + contexte
        background = BackgroundTasks()
        background.add_task(
            _enqueue_skill_enrichment,
            user_id=str(current_user.id),
            skill_type=skill_type,
            matiere=payload.params.get("matiere"),
            succes=result.success,
        )
        # Background: extraction des concepts du chat vers le graphe cognitif
        background.add_task(
            _enqueue_concept_extraction,
            user_id=str(current_user.id),
            user_message=payload.prompt,
            llm_response=result.content or "",
        )
        # Background: détection contexte (urgence, préférences) depuis le message
        background.add_task(
            _detect_context_from_chat,
            user_id=str(current_user.id),
            message=payload.prompt,
        )

        return SkillResultResponse.from_skill_result(
            result=result,
            session_id=session_id,
        )

    except HTTPException:
        await idempotency.liberrer_key(idempotency_key)
        raise
    except Exception as e:
        logger.error(f"Skill execution failed: {e}", exc_info=True)
        await idempotency.liberrer_key(idempotency_key)
        raise HTTPException(status_code=422, detail="SKILL_FAILED")


@router.post(
    "/quiz/{quiz_session_id}/soumettre",
    response_model=QuizCorrectionResponse,
    summary="Soumettre les réponses d'un quiz",
    description="""
**Soumet les réponses d'un quiz et obtient la correction détaillée.**

**Requis :**
- `quiz_session_id` : l'ID de la session de quiz (retourné par `POST /skills/run`)
- `reponses` : liste des réponses de l'utilisateur (index des options choisies)
- `duree_secondes` : temps mis pour répondre (optionnel)

**Ce que retourne l'endpoint :**
- `score_percent` : score en pourcentage
- `corrections` : détail question par question (bonne réponse, explication)
- `lacunes_detectees` : notions où l'utilisateur a échoué (mis à jour dans le graphe cognitif)
- `lacune_detectee` : la notion principale à réviser

**Effet de bord :** le profil cognitif de l'utilisateur est automatiquement enrichi avec les lacunes détectées.
    """,
)
async def submit_quiz_answers(
    quiz_session_id: str,
    payload: QuizSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    correction_service=Depends(get_quiz_correction_service),
):
    """Submit quiz answers → correction + cognitive graph enrichment."""
    from uuid import UUID

    quiz_session = (
        db.query(QuizSession)
        .filter(
            QuizSession.id == UUID(quiz_session_id),
            QuizSession.user_id == current_user.id,
        )
        .first()
    )

    if not quiz_session:
        raise HTTPException(status_code=404, detail="QUIZ_NOT_FOUND")

    if quiz_session.is_submitted:
        raise HTTPException(status_code=409, detail="QUIZ_ALREADY_SUBMITTED")

    result = await correction_service.corriger(
        quiz_session_id=quiz_session_id,
        reponses_utilisateur=payload.reponses,
        duree_secondes=payload.duree_secondes,
    )

    # Background: enrichir le profil avec les lacunes détectées
    background_tasks.add_task(
        _enqueue_quiz_enrichment,
        user_id=str(current_user.id),
        matiere=result.get("matiere"),
        score=result.get("score_percent", 0),
        lacune_notion=result.get("lacune_detectee"),
    )

    return QuizCorrectionResponse(**result)


@router.get(
    "/liste",
    response_model=SkillListResponse,
    dependencies=[Depends(get_rate_limiter_dependency(skills_list_rate_limiter))],
)
async def list_available_skills(
    current_user: User = Depends(get_current_user),
):
    """Catalogue des skills disponibles selon le plan utilisateur."""
    skills = []
    for skill_type, info in SKILL_CATALOG.items():
        disponible = _is_plan_sufficient(current_user.plan_effectif, info["plan_requis"])
        skills.append({
            "type": skill_type,
            "nom": info["nom"],
            "description": info["description"],
            "output_type": info["output_type"],
            "plan_requis": info["plan_requis"],
            "disponible": disponible,
            "raison_indisponible": None if disponible else f"Plan {info['plan_requis'].capitalize()} requis",
            "exemple_prompt": info["exemple_prompt"],
        })

    return {"skills": skills}


@router.post(
    "/detecter",
    response_model=IntentDetectionResponse,
    dependencies=[Depends(get_rate_limiter_dependency(skills_detect_rate_limiter))],
)
async def detect_skill_intention(
    payload: DetectIntentRequest,
    dispatcher=Depends(get_skill_dispatcher),
):
    """Détecte l'intention d'un prompt sans l'exécuter."""
    import re

    skill_detected, method = dispatcher._detecter_regex(payload.texte)

    if not skill_detected:
        skill_detected = await dispatcher._classifier_llm(payload.texte)
        method = "llm" if skill_detected else None

    # Extraction paramètres basique
    params = {}
    if skill_detected:
        if match := re.search(r"(Mathématiques|Physique|Chimie|SVT|Français|Anglais|Philosophie|Histoire)", payload.texte, re.I):
            params["matiere"] = match.group(1)
        if match := re.search(r"(Tle|Terminale|Première|Seconde|3ème|Troisième|Form \d+)", payload.texte, re.I):
            params["niveau"] = match.group(1)

    return {
        "skill_detecte": skill_detected,
        "confidence": "high" if method == "regex" else "medium" if method == "llm" else "low",
        "methode": method or "fallback",
        "params_extraits": params,
        "alternatives": ["tuteur"] if not skill_detected else [],
    }


def _enqueue_skill_enrichment(user_id: str, skill_type: str, matiere: str, succes: bool):
    """Enqueue skill enrichment task for user profile."""
    try:
        from app.modules.skills.jobs.tasks import enrich_profile_after_skill_task
        enrich_profile_after_skill_task.delay(
            user_id=user_id,
            skill_type=skill_type,
            matiere=matiere,
            succes=succes,
        )
    except Exception as e:
        logger.warning(f"Failed to enqueue skill enrichment: {e}")


def _enqueue_quiz_enrichment(user_id: str, matiere: str, score: float, lacune_notion: str = None):
    """Enqueue quiz correction enrichment task for user profile (lacunes + scores)."""
    try:
        from app.modules.skills.jobs.tasks import enrich_profile_after_skill_task
        enrich_profile_after_skill_task.delay(
            user_id=user_id,
            skill_type="quiz",
            matiere=matiere,
            succes=score >= 50,
            score=score,
            lacune_notion=lacune_notion,
        )
    except Exception as e:
        logger.warning(f"Failed to enqueue quiz enrichment: {e}")


def _enqueue_concept_extraction(user_id: str, user_message: str, llm_response: str):
    """Enqueue concept extraction task for cognitive graph enrichment."""
    try:
        from app.modules.memory.jobs.tasks import extract_concepts_from_chat_task
        extract_concepts_from_chat_task.delay(
            message_id=0,  # Placeholder — le message_id réel n'est pas critique
            user_id=user_id,
            user_message=user_message,
            llm_response=llm_response,
        )
    except Exception as e:
        logger.warning(f"Failed to enqueue concept extraction: {e}")
