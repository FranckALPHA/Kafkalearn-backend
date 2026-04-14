"""
routes/coach.py
===============
Endpoints du Coach IA — recommandations personnalisées et planning d'étude.
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
from app.modules.users.services.coach_service import CoachService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/coach", tags=["Coach IA"])


@router.get("/recommendation")
async def get_recommendation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Recommandation personnalisée du Coach IA.

    Combine graphe cognitif + 4 couches de signaux pour décider :
    - QUOI réviser (concept, matière)
    - COMMENT (fiche, quiz, exercice)
    - Message motivationnel personnalisé
    """
    from app.modules.memory.services.concept_graph_service import ConceptGraphService

    coach = CoachService(db)
    graph_svc = ConceptGraphService(db)

    recommendation = await coach.get_personalized_recommendation(
        user_id=str(current_user.id),
        concept_graph_service=graph_svc,
    )

    return recommendation


@router.get("/study-plan")
async def get_study_plan(
    days: int = Query(7, ge=1, le=30, description="Nombre de jours devant"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Planning de révision intelligent sur N jours.

    Applique l'interleaving (mélange des matières) et respecte
    les habitudes temporelles de l'utilisateur.
    """
    from app.modules.memory.services.concept_graph_service import ConceptGraphService

    coach = CoachService(db)
    graph_svc = ConceptGraphService(db)

    plan = await coach.generate_study_plan(
        user_id=str(current_user.id),
        days_ahead=days,
        concept_graph_service=graph_svc,
    )

    return {
        "days": days,
        "total_sessions": len(plan),
        "sessions": plan,
    }


@router.get("/signals")
async def get_learning_signals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne les 4 couches de signaux d'apprentissage de l'utilisateur.
    Utile pour le dashboard et la transparence.
    """
    coach = CoachService(db)
    signals = coach._get_signals(str(current_user.id))
    return signals.serialize()


@router.post("/signals/context")
async def update_context_from_chat(
    message: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Détecte le contexte depuis un message chat et met à jour les signaux.
    Appelée en background après chaque message de l'utilisateur.
    """
    coach = CoachService(db)
    coach.detect_context_from_chat(str(current_user.id), message)
    return {"status": "context_updated"}
