from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from .dependencies import get_rate_limiter_dependency, get_current_user, get_db
from schemas.requests import SkillRunRequest, QuizSubmitRequest
from schemas.responses import SkillResultResponse, QuizCorrectionResponse
from services.skill_dispatcher import SkillDispatcher
from services.quiz_correction_service import QuizCorrectionService
from services.idempotency_service import IdempotencyService

router = APIRouter(prefix="/skills", tags=["skills"])

@router.post("/run", response_model=SkillResultResponse, dependencies=[Depends(get_rate_limiter_dependency("skills_run"))])
async def run_skill(
    request: Request,
    payload: SkillRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    dispatcher: SkillDispatcher = Depends(get_skill_dispatcher),
    idempotency: IdempotencyService = Depends(get_idempotency_service)
):
    """
    Point d'entrée principal pour exécuter un skill.
    Rate limited: 10 req/min par utilisateur.
    """
    # ─── 1. Vérification idempotency ────────────────────────────
    idempotency_key = payload.idempotency_key or idempotency.generer_key_auto(
        user_id=str(current_user.id),
        prompt=payload.prompt,
        skill_type=payload.skill
    )
    
    is_duplicate, previous_result = await idempotency.verifier_et_reserver(
        key=idempotency_key,
        ttl_seconds=60  # fenêtre de déduplication
    )
    
    if is_duplicate and previous_result:
        raise HTTPException(409, "IDEMPOTENCY_DUPLICATE", headers={"X-Original-Request-Id": idempotency_key})
    
    try:
        # ─── 2. Dispatch vers le bon skill ───────────────────────
        skill_instance, skill_type, detection_method = await dispatcher.dispatch(
            prompt=payload.prompt,
            skill_explicite=payload.skill,
            user_params=payload.params,
            user_plan=current_user.plan_effectif
        )
        
        # ─── 3. Exécution du skill ───────────────────────────────
        skill_request = SkillRequest(
            user_id=str(current_user.id),
            prompt=payload.prompt,
            chat_session_id=payload.chat_session_id,
            langue=payload.langue or current_user.langue,
            params=payload.params,
            avec_rag=payload.avec_rag,
            user_document_id=payload.user_document_id,
            historique_session=[]  # à charger via ChatService si session fournie
        )
        
        result = await skill_instance.run(skill_request)
        
        # ─── 4. Persistance et background tasks ──────────────────
        from services.chat_service import ChatService
        chat_service = ChatService(db)
        
        # Création/MAJ session
        session_id = payload.chat_session_id or (await chat_service.creer_session(
            user_id=str(current_user.id),
            titre=payload.prompt[:50]
        )).id
        
        # Sauvegarde messages user + assistant
        await chat_service.ajouter_message_pair(
            session_id=session_id,
            user_content=payload.prompt,
            assistant_result=result,
            skill_type=skill_type,
            matiere=payload.params.get("matiere")
        )
        
        # Marquer idempotency comme complète
        await idempotency.marquer_complete(idempotency_key, result.dict())
        
        # Background: enrichissement profil + analytics
        BackgroundTasks().add_task(
            enrich_profile_after_skill_task.delay,
            user_id=str(current_user.id),
            skill_type=skill_type,
            matiere=payload.params.get("matiere"),
            succes=result.success
        )
        
        return SkillResultResponse.from_skill_result(
            result=result,
            message_id=...,  # ID du message assistant créé
            session_id=session_id,
            quota_restant=await get_quota_remaining(current_user)
        )
        
    except HTTPException:
        await idempotency.liberrer_key(idempotency_key)
        raise
    except Exception as e:
        logger.error(f"Skill execution failed: {e}", exc_info=True)
        await idempotency.liberrer_key(idempotency_key)
        raise HTTPException(422, "SKILL_FAILED", detail=str(e))

@router.post("/quiz/{quiz_session_id}/soumettre", response_model=QuizCorrectionResponse)
async def submit_quiz_answers(
    quiz_session_id: str,
    payload: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    correction_service: QuizCorrectionService = Depends(get_quiz_correction_service)
):
    """
    Soumission des réponses d'un quiz et obtention de la correction.
    """
    # Vérification ownership
    quiz_session = db.query(QuizSession).filter(
        QuizSession.id == quiz_session_id,
        QuizSession.user_id == current_user.id
    ).first()
    
    if not quiz_session:
        raise HTTPException(404, "QUIZ_NOT_FOUND")
    
    if quiz_session.submitted_at:
        raise HTTPException(409, "QUIZ_ALREADY_SUBMITTED")
    
    # Correction
    result = await correction_service.corriger(
        quiz_session_id=quiz_session_id,
        reponses_utilisateur=payload.reponses,
        duree_secondes=payload.duree_secondes
    )
    
    # Background: détection lacunes + suggestions
    if result.lacune_detectee:
        BackgroundTasks().add_task(
            notifier_lacune_detectee_task.delay,
            user_id=str(current_user.id),
            matiere=result.matiere,
            notion=result.lacune_detectee
        )
    
    return result

@router.get("/liste", dependencies=[Depends(get_rate_limiter_dependency("skills_list"))])
async def list_available_skills(
    current_user: User = Depends(get_current_user)
):
    """
    Catalogue des skills disponibles selon le plan utilisateur.
    """
    from utils.constants import SKILL_CATALOG
    
    skills = []
    for skill_type, info in SKILL_CATALOG.items():
        disponible = is_plan_sufficient(current_user.plan_effectif, info["plan_requis"])
        skills.append({
            "type": skill_type,
            "nom": info["nom"],
            "description": info["description"],
            "output_type": info["output_type"],
            "plan_requis": info["plan_requis"],
            "disponible": disponible,
            "raison_indisponible": None if disponible else f"Plan {info['plan_requis'].capitalize()} requis",
            "exemple_prompt": info["exemple_prompt"]
        })
    
    return {"skills": skills}

@router.post("/detecter", dependencies=[Depends(get_rate_limiter_dependency("skills_detect"))])
async def detect_skill_intention(
    payload: DetectIntentRequest,
    dispatcher: SkillDispatcher = Depends(get_skill_dispatcher)
):
    """
    Détecte l'intention d'un prompt sans l'exécuter.
    Utile pour l'auto-complétion ou la prévisualisation.
    """
    skill_detected, method = dispatcher._detecter_regex(payload.texte)
    
    if not skill_detected:
        skill_detected = await dispatcher._classifier_llm(payload.texte)
        method = "llm" if skill_detected else None
    
    # Extraction paramètres basique
    params = {}
    if skill_detected:
        # Regex simple pour extraire matière/niveau
        import re
        if match := re.search(r'(Mathématiques|Physique|Chimie|SVT)', payload.texte, re.I):
            params["matiere"] = match.group(1)
        if match := re.search(r'(Tle|3ème|Form \d+)', payload.texte, re.I):
            params["niveau"] = match.group(1)
    
    return {
        "skill_detecte": skill_detected,
        "confidence": "high" if method == "regex" else "medium" if method == "llm" else "low",
        "methode": method,
        "params_extraits": params,
        "alternatives": ["tuteur"] if not skill_detected else []
    }