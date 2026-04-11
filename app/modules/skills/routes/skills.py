"""
routes/skills.py
================
Endpoints principaux pour l'exécution des skills.
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
)
async def run_skill(
    payload: SkillRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    dispatcher=Depends(get_skill_dispatcher),
    idempotency=Depends(get_idempotency_service),
):
    """
    Point d'entrée principal pour exécuter un skill.
    Rate limited: 10 req/min par utilisateur.
    """
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

        # Background: enrichissement profil
        background = BackgroundTasks()
        background.add_task(
            _enqueue_skill_enrichment,
            user_id=str(current_user.id),
            skill_type=skill_type,
            matiere=payload.params.get("matiere"),
            succes=result.success,
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
)
async def submit_quiz_answers(
    quiz_session_id: str,
    payload: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    correction_service=Depends(get_quiz_correction_service),
):
    """Soumission des réponses d'un quiz et obtention de la correction."""
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
