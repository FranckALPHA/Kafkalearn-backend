"""
routes/admin.py (memory module)
===============================
Endpoints admin pour la gestion du graphe cognitif global.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.memory.routes.dependencies import (
    get_db,
    get_current_user,
    get_rate_limiter_dependency,
)
from app.modules.users.models import User
from app.modules.memory.services.concept_graph_service import ConceptGraphService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory/admin", tags=["Memory Admin - Graph"])


def _require_superadmin(current_user: User):
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="ADMIN_REQUIRED")


@router.get("/graph/global")
async def get_global_graph(
    relation: Optional[str] = Query(None, description="Filtrer par type de relation"),
    matiere: Optional[str] = Query(None, description="Filtrer par matière"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liste les arêtes du graphe cognitif global (couche programme).
    Utilisé pour la validation manuelle des prérequis détectés par le LLM.
    """
    _require_superadmin(current_user)

    graph_svc = ConceptGraphService(db)
    edges = graph_svc.get_edges(
        user_id=None,  # Global only
        relation=relation,
        matiere=matiere,
        min_confidence=min_confidence,
        limit=limit,
    )

    return {
        "edges": edges,
        "total": len(edges),
    }


@router.post("/graph/global/{edge_id}/validate")
async def validate_edge(
    edge_id: str,
    is_valid: bool,
    corrected_relation: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Valide, corrige ou supprime une arête du graphe global.
    is_valid=False → supprime l'arête
    corrected_relation → modifie le type de relation
    """
    _require_superadmin(current_user)

    from app.modules.memory.jobs.tasks import validate_global_graph_edge_task

    result = validate_global_graph_edge_task.delay(
        edge_id=edge_id,
        is_valid=is_valid,
        corrected_relation=corrected_relation,
    )
    return {"task_id": result.id, "status": "queued"}


@router.get("/graph/global/stats")
async def get_global_graph_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Statistiques du graphe cognitif global."""
    _require_superadmin(current_user)

    rows = db.execute(text("""
        SELECT relation, COUNT(*) as count, AVG(confidence) as avg_conf
        FROM concept_graph
        WHERE user_id IS NULL
        GROUP BY relation
        ORDER BY count DESC
    """)).fetchall()

    total = db.execute(text("SELECT COUNT(*) FROM concept_graph WHERE user_id IS NULL")).scalar()

    matieres = db.execute(text("""
        SELECT matiere, COUNT(*) as count
        FROM concept_graph
        WHERE user_id IS NULL AND matiere IS NOT NULL
        GROUP BY matiere
        ORDER BY count DESC
    """)).fetchall()

    return {
        "total_edges": total,
        "by_relation": [{"relation": r[0], "count": r[1], "avg_confidence": round(float(r[2]), 3)} for r in rows],
        "by_matiere": [{"matiere": m[0], "count": m[1]} for m in matieres],
    }
