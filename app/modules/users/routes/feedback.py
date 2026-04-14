"""
routes/feedback.py
==================
Endpoints de feedback explicite — l'utilisateur dit directement ce qu'il pense.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.modules.users.routes.dependencies import (
    get_db,
    get_current_user,
)
from app.modules.users.models import User
from app.modules.users.models.user_feedback import UserFeedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/feedback", tags=["Feedback"])


@router.post("/")
async def submit_feedback(
    feedback_type: str,
    rating: float = Query(None, ge=1, le=5),
    comment: str = None,
    related_entity_type: str = None,
    related_entity_id: int = None,
    matiere: str = None,
    concept: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Soumettre un feedback explicite.

    Types de feedback :
    - content_format : préférence de format (schémas, textes, vidéos)
    - content_difficulty : trop facile / trop difficile
    - session_quality : cette session m'a aidé / pas aidé
    - coach_message : ton message était motivant / décourageant
    - system_suggestion : cette recommandation était pertinente / pas
    """
    feedback = UserFeedback(
        user_id=current_user.id,
        feedback_type=feedback_type,
        rating=rating,
        comment=comment,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        matiere=matiere,
        concept=concept,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Mettre à jour les signaux comportementaux en fonction du feedback
    action = _apply_feedback_to_signals(db, str(current_user.id), feedback)

    return {
        "id": feedback.id,
        "status": "received",
        "action_taken": action,
    }


@router.get("/history")
async def get_feedback_history(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Historique des feedbacks de l'utilisateur."""
    feedbacks = (
        db.query(UserFeedback)
        .filter(UserFeedback.user_id == current_user.id)
        .order_by(UserFeedback.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "feedbacks": [f.serialize() for f in feedbacks],
        "total": len(feedbacks),
    }


@router.get("/stats")
async def get_feedback_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Statistiques des feedbacks."""
    from sqlalchemy import func

    # Par type
    by_type = (
        db.query(UserFeedback.feedback_type, func.count(UserFeedback.id))
        .filter(UserFeedback.user_id == current_user.id)
        .group_by(UserFeedback.feedback_type)
        .all()
    )

    # Moyenne de rating
    avg_rating = (
        db.query(func.avg(UserFeedback.rating))
        .filter(
            UserFeedback.user_id == current_user.id,
            UserFeedback.rating.isnot(None),
        )
        .scalar()
    )

    return {
        "by_type": [{"type": t, "count": c} for t, c in by_type],
        "avg_rating": round(float(avg_rating), 2) if avg_rating else None,
        "total_feedbacks": (
            db.query(func.count(UserFeedback.id))
            .filter(UserFeedback.user_id == current_user.id)
            .scalar()
        ),
    }


def _apply_feedback_to_signals(db: Session, user_id: str, feedback: UserFeedback) -> str:
    """Applique le feedback aux signaux comportementaux immédiatement."""
    from app.modules.users.services.coach_service import CoachService

    coach = CoachService(db)
    signals = coach._get_signals(user_id)
    behavioral = signals.behavioral_signals or {}
    contextual = signals.contextual_signals or {}
    action = "noted_for_coach"

    if feedback.feedback_type == "content_format":
        prefs = contextual.get("explicit_preferences", {})
        comment_lower = (feedback.comment or "").lower()
        if "schéma" in comment_lower or "image" in comment_lower or "visuel" in comment_lower:
            prefs["prefers_schemas"] = feedback.rating >= 3
        if "texte" in comment_lower or "lire" in comment_lower:
            prefs["hates_long_texts"] = feedback.rating < 3
        if "quiz" in comment_lower or "exercice" in comment_lower:
            behavioral["content_preference"] = "exercises" if feedback.rating >= 3 else "fiches"
        contextual["explicit_preferences"] = prefs
        action = "updated_content_preference"

    elif feedback.feedback_type == "content_difficulty":
        if feedback.rating <= 2:
            behavioral["preferred_difficulty"] = "easy"
        elif feedback.rating >= 4:
            behavioral["preferred_difficulty"] = "hard"
        action = "adjusted_difficulty"

    elif feedback.feedback_type == "session_quality":
        if feedback.rating >= 4:
            behavioral["session_satisfaction"] = behavioral.get("session_satisfaction", 0.5) + 0.1
        elif feedback.rating <= 2:
            behavioral["session_satisfaction"] = behavioral.get("session_satisfaction", 0.5) - 0.1
        action = "updated_session_satisfaction"

    elif feedback.feedback_type == "coach_message":
        if feedback.rating >= 4:
            behavioral["coach_message_receptivity"] = "high"
        elif feedback.rating <= 2:
            behavioral["coach_message_receptivity"] = "low"
        action = "updated_coach_receptivity"

    elif feedback.feedback_type == "system_suggestion":
        if feedback.rating >= 4:
            behavioral["recommendation_trust"] = behavioral.get("recommendation_trust", 0.5) + 0.1
        elif feedback.rating <= 2:
            behavioral["recommendation_trust"] = behavioral.get("recommendation_trust", 0.5) - 0.1
        action = "updated_recommendation_trust"

    # Appliquer les limites
    behavioral["session_satisfaction"] = max(0, min(1, behavioral.get("session_satisfaction", 0.5)))
    behavioral["recommendation_trust"] = max(0, min(1, behavioral.get("recommendation_trust", 0.5)))

    signals.behavioral_signals = behavioral
    signals.contextual_signals = contextual
    db.commit()

    feedback.action_taken = action
    db.commit()

    return action
