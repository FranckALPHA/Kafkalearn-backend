"""
routes/memory.py
================
User-facing memory routes.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.modules.memory.schemas import (
    AnswerSubmitRequest,
    SectionCompleteRequest,
    SectionListResponse,
    SectionItemsResponse,
    ReviewTodayResponse,
    MemoryStatsResponse,
)
from app.modules.memory.routes.dependencies import (
    get_db,
    get_current_user,
    get_rate_limiter_dependency,
    get_generator_service,
    get_grader_service,
    get_scheduler_service,
    get_stats_service,
    memory_rate_limiter,
    memory_submit_rate_limiter,
)
from app.modules.memory.models import MemorySection, MemoryItem, UserSectionProgress, MemoryItemAttempt
from app.modules.memory.services.spaced_repetition_scheduler import SpacedRepetitionScheduler
from app.modules.users.models import User
from app.modules.memory.services.memory_generator_service import MemoryGeneratorService
from app.modules.memory.services.grader_service import GraderService
from app.modules.memory.services.memory_stats_service import MemoryStatsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["Memory"])


# -------------------------------------------------------------------
# GET /memory/sections — list sections for a document with user progress
# -------------------------------------------------------------------
@router.get("/sections", response_model=SectionListResponse)
async def list_sections(
    document_id: int = Query(..., description="Document ID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limited: bool = Depends(get_rate_limiter_dependency(memory_rate_limiter)),
):
    """List all memory sections for a document with user progress."""
    sections = (
        db.query(MemorySection)
        .filter(
            MemorySection.document_id == document_id,
            MemorySection.generation_status.in_(["complete", "partial"]),
        )
        .order_by(MemorySection.section_order)
        .all()
    )

    if not sections:
        raise HTTPException(status_code=404, detail="No sections found for this document")

    # Fetch user progress for all sections
    section_ids = [s.id for s in sections]
    progress_records = (
        db.query(UserSectionProgress)
        .filter(
            UserSectionProgress.user_id == str(user.id),
            UserSectionProgress.section_id.in_(section_ids),
        )
        .all()
    )
    progress_map = {p.section_id: p for p in progress_records}

    sections_data = []
    total_progress = 0.0
    for section in sections:
        progress = progress_map.get(section.id)
        item = section.serialize_list_item(user_progress=progress)
        sections_data.append(item)
        if progress:
            total_progress += progress.progression or 0.0

    progression_globale = total_progress / len(sections) if sections else 0.0

    # Get document titre from first section
    doc = sections[0].document if sections else None
    document_titre = doc.titre if doc else "Unknown"

    return SectionListResponse(
        document_id=document_id,
        document_titre=document_titre,
        nb_sections=len(sections),
        progression_globale=round(progression_globale, 2),
        sections=sections_data,
    )


# -------------------------------------------------------------------
# GET /memory/sections/{section_id}/items — items for review (no verso)
# -------------------------------------------------------------------
@router.get("/sections/{section_id}/items", response_model=SectionItemsResponse)
async def get_section_items(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limited: bool = Depends(get_rate_limiter_dependency(memory_rate_limiter)),
):
    """Get items for a section, stripped of verso/answer."""
    section = db.query(MemorySection).filter(MemorySection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="SECTION_NOT_FOUND")

    # Get or create user progress
    progress = (
        db.query(UserSectionProgress)
        .filter(
            UserSectionProgress.user_id == str(user.id),
            UserSectionProgress.section_id == section_id,
        )
        .first()
    )
    if not progress:
        progress = UserSectionProgress(
            user_id=str(user.id),
            section_id=section_id,
            current_index=0,
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    # Get items (sorted for review order)
    items = (
        db.query(MemoryItem)
        .filter(MemoryItem.section_id == section_id)
        .order_by(MemoryItem.id)
        .all()
    )

    # Serialize items without verso/answer
    items_data = []
    for idx, item in enumerate(items):
        content = item.content_json or {}
        item_data = {
            "id": item.id,
            "item_type": item.item_type,
            "recto": content.get("fr", {}).get("recto") or content.get("fr", {}).get("question") or content.get("fr", {}).get("enonce", ""),
            "index": idx,
        }
        # For QCM, include options but not the correct answer
        if item.item_type == "qcm":
            item_data["options"] = content.get("fr", {}).get("options", [])
        # For cloze, include the text with blanks
        elif item.item_type == "cloze":
            item_data["enonce"] = content.get("fr", {}).get("enonce", "")
            item_data["alternatives_count"] = len(content.get("fr", {}).get("alternatives", "").split("|"))

        items_data.append(item_data)

    # Determine language
    langue = "fr"

    return SectionItemsResponse(
        section_id=section_id,
        section_title=section.section_title,
        nb_items=len(items),
        langue=langue,
        current_index=progress.current_index,
        items=items_data,
    )


# -------------------------------------------------------------------
# GET /memory/sections/{section_id}/items/{item_id}/verso — reveal answer
# -------------------------------------------------------------------
@router.get("/sections/{section_id}/items/{item_id}/verso")
async def get_item_verso(
    section_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _rate_limited: bool = Depends(get_rate_limiter_dependency(memory_rate_limiter)),
):
    """Reveal the flashcard answer/verso for a specific item."""
    item = (
        db.query(MemoryItem)
        .filter(MemoryItem.id == item_id, MemoryItem.section_id == section_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="ITEM_NOT_FOUND")

    content = item.content_json or {}
    fr_content = content.get("fr", {})

    verso_data = {
        "item_id": item_id,
        "item_type": item.item_type,
    }

    if item.item_type == "flashcard":
        verso_data["verso"] = fr_content.get("verso", "")
    elif item.item_type == "qcm":
        verso_data["bonne_reponse"] = fr_content.get("bonne_reponse", "")
        verso_data["explication"] = fr_content.get("explication", "")
    elif item.item_type == "cloze":
        verso_data["alternatives"] = fr_content.get("alternatives", "")
    elif item.item_type == "short_answer":
        verso_data["bonne_reponse"] = fr_content.get("bonne_reponse", "")
        verso_data["explication"] = fr_content.get("explication", "")

    return verso_data


# -------------------------------------------------------------------
# POST /memory/sections/{section_id}/items/{item_id}/repondre — submit answer
# -------------------------------------------------------------------
@router.post("/sections/{section_id}/items/{item_id}/repondre")
async def submit_answer(
    section_id: int,
    item_id: int,
    body: AnswerSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    grader_service: GraderService = Depends(get_grader_service),
    _rate_limited: bool = Depends(get_rate_limiter_dependency(memory_submit_rate_limiter)),
):
    """Grade a user answer, save attempt, update progress."""
    # Fetch item
    item = (
        db.query(MemoryItem)
        .filter(MemoryItem.id == item_id, MemoryItem.section_id == section_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="ITEM_NOT_FOUND")

    # Grade the answer
    grading = await grader_service.noter(
        item=item,
        reponse_utilisateur=body.reponse,
        qualite_flashcard=body.qualite,
    )

    # Save attempt
    attempt = MemoryItemAttempt(
        user_id=str(user.id),
        item_id=item_id,
        section_id=section_id,
        reponse_utilisateur=body.reponse,
        qualite_reponse=body.qualite if body.qualite is not None else grading["score"],
        score_obtenu=grading["score"],
        est_correct=grading["est_correct"],
        duree_secondes=body.duree_secondes,
        grading_details=grading,
    )
    db.add(attempt)

    # Update progress
    progress = (
        db.query(UserSectionProgress)
        .filter(
            UserSectionProgress.user_id == str(user.id),
            UserSectionProgress.section_id == section_id,
        )
        .first()
    )
    if progress:
        progress.last_reviewed_at = datetime.now(timezone.utc)
        if progress.current_index is not None:
            progress.current_index = min(progress.current_index + 1, item.nb_items or 999)

        # Update score (running average)
        attempts = (
            db.query(MemoryItemAttempt)
            .filter(
                MemoryItemAttempt.user_id == str(user.id),
                MemoryItemAttempt.section_id == section_id,
            )
            .all()
        )
        if attempts:
            avg_score = sum(a.score_obtenu for a in attempts) / len(attempts)
            progress.score_section = round(avg_score, 2)
            total_items = progress.current_index or len(attempts)
            progress.progression = round(total_items / max(len(db.query(MemoryItem).filter(MemoryItem.section_id == section_id).all()) or 1, 1) * 100, 2)

    db.commit()

    # Background: enrichir les signaux cognitifs + le graphe cognitif (Coach IA)
    background_tasks.add_task(
        _enrich_cognitive_signals,
        user_id=str(user.id),
        matiere=item.section.document.matiere if item.section and item.section.document else None,
        score=grading["score"],
        difficulty="hard" if grading["score"] < 40 else "medium" if grading["score"] < 70 else "easy",
        completed=grading["est_correct"],
        section_id=section_id,
        item_id=item_id,
    )

    return {
        "item_id": item_id,
        "score": grading["score"],
        "est_correct": grading["est_correct"],
        "details": grading.get("details", ""),
    }


# -------------------------------------------------------------------
# POST /memory/sections/{section_id}/complete — mark section completed
# -------------------------------------------------------------------
@router.post("/sections/{section_id}/complete")
async def complete_section(
    section_id: int,
    body: SectionCompleteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scheduler_service: SpacedRepetitionScheduler = Depends(get_scheduler_service),
    _rate_limited: bool = Depends(get_rate_limiter_dependency(memory_submit_rate_limiter)),
):
    """Mark a section as completed and calculate SM-2 next review."""
    section = db.query(MemorySection).filter(MemorySection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="SECTION_NOT_FOUND")

    # Get or create progress
    progress = (
        db.query(UserSectionProgress)
        .filter(
            UserSectionProgress.user_id == str(user.id),
            UserSectionProgress.section_id == section_id,
        )
        .first()
    )
    if not progress:
        raise HTTPException(status_code=404, detail="PROGRESS_NOT_FOUND")

    # Mark as completed
    progress.is_completed = True
    progress.completed_at = datetime.now(timezone.utc)
    progress.progression = 100.0
    db.commit()

    # Calculate SM-2 next review (use avg quality from attempts)
    avg_qualite = (
        db.query(MemoryItemAttempt.qualite_reponse)
        .filter(
            MemoryItemAttempt.user_id == str(user.id),
            MemoryItemAttempt.section_id == section_id,
        )
    )
    avg_qualite_rows = avg_qualite.all()
    qualite_moyenne = (
        sum(r[0] for r in avg_qualite_rows if r[0] is not None) / len(avg_qualite_rows)
        if avg_qualite_rows
        else 3
    )

    result = await scheduler_service.calculer_prochaine_revision(
        user_id=str(user.id),
        section_id=section_id,
        qualite_reponse=int(qualite_moyenne),
    )

    return {
        "section_id": section_id,
        "is_completed": True,
        "completed_at": progress.completed_at.isoformat(),
        "next_review": result.next_review_date.isoformat() if result.next_review_date else None,
        "interval_days": result.interval_days,
        "easiness_factor": result.easiness_factor,
    }


# -------------------------------------------------------------------
# GET /memory/today — sections due for review today
# -------------------------------------------------------------------
@router.get("/today", response_model=ReviewTodayResponse)
async def get_today_reviews(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    scheduler_service: SpacedRepetitionScheduler = Depends(get_scheduler_service),
    _rate_limited: bool = Depends(get_rate_limiter_dependency(memory_rate_limiter)),
):
    """Get sections due for review today."""
    sections_due = await scheduler_service.obtenir_sections_a_revoir(
        user_id=str(user.id),
        grace_hours=24,
    )

    sections_data = []
    temps_total = 0
    for s in sections_due:
        section_info = s.get("section", {})
        progress_info = s.get("progress", {})
        sections_data.append({
            "section_id": section_info.get("id"),
            "section_title": section_info.get("section_title", ""),
            "urgence": s.get("urgence", "normal"),
            "nb_items": section_info.get("nb_items", 0),
            "progression": progress_info.get("progression", 0),
            "next_review_at": progress_info.get("next_review_at"),
        })
        # Estimate ~1 min per item
        temps_total += section_info.get("nb_items", 0)

    return ReviewTodayResponse(
        nb_sections_a_revoir=len(sections_due),
        temps_estime_minutes=temps_total,
        sections=sections_data,
    )


# -------------------------------------------------------------------
# GET /memory/stats — user memory stats
# -------------------------------------------------------------------
@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    stats_service: MemoryStatsService = Depends(get_stats_service),
    _rate_limited: bool = Depends(get_rate_limiter_dependency(memory_rate_limiter)),
):
    """Get user's memory statistics."""
    stats = await stats_service.calculer_stats_utilisateur(user_id=str(user.id))
    return MemoryStatsResponse(**stats)


# ────────────────────────────────────────────────────────────────
# Background enrichment (post-response, non bloquant)
# ────────────────────────────────────────────────────────────────

def _enrich_cognitive_signals(user_id: str, matiere: str, score: float, difficulty: str, completed: bool,
                              section_id: int = None, item_id: int = None):
    """
    Enrichit les signaux cognitifs ET le graphe cognitif après une réponse memory.
    Deux couches mises à jour :
    1. UserLearningSignals (4 couches : temporel, comportemental, cognitif, contextuel)
    2. concept_graph (A_ECHOUE_SUR / MAITRISE lié au concept de la section)
    """
    try:
        from app.core.database import SessionLocal
        from app.modules.users.services.coach_service import CoachService

        db = SessionLocal()
        coach = CoachService(db)

        # Couche 1 : signaux d'apprentissage
        coach.record_session(
            user_id=user_id,
            duration_min=5,
            matiere=matiere or "general",
            score=score,
            difficulty=difficulty,
            completed=completed,
        )

        # Couche 2 : graphe cognitif (concept_graph)
        if section_id:
            from app.modules.memory.models import MemorySection
            from app.modules.memory.services.concept_graph_service import ConceptGraphService

            section = db.query(MemorySection).filter(MemorySection.id == section_id).first()
            if section:
                graph_svc = ConceptGraphService(db)
                # Le concept = le titre de la section (ex: "EXERCICE 1: Dérivées")
                concept = section.section_title
                # Extraire la notion principale du titre
                notion = concept.split(":")[-1].strip() if ":" in concept else concept
                notion = notion[:100]  # Limiter la longueur

                if score < 50:
                    # Échec → arête A_ECHOUE_SUR
                    graph_svc.add_edge(
                        user_id=user_id,
                        source=notion,
                        target=notion,
                        relation="A_ECHOUE_SUR",
                        confidence=min(score / 50.0, 1.0),
                        source_type="memory",
                        matiere=matiere,
                        canonical_name=notion,
                        context=f"section_id={section_id}, item_id={item_id}, score={score}",
                    )
                elif score >= 75:
                    # Succès → arête MAITRISE
                    graph_svc.add_edge(
                        user_id=user_id,
                        source=notion,
                        target=notion,
                        relation="MAITRISE",
                        confidence=score / 100.0,
                        source_type="memory",
                        matiere=matiere,
                        canonical_name=notion,
                        context=f"section_id={section_id}, item_id={item_id}, score={score}",
                    )

        db.commit()
        db.close()
    except Exception as e:
        logging.getLogger(__name__).warning(f"Failed to enrich cognitive signals: {e}")
