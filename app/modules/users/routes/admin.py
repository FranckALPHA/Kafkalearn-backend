"""
routes/admin.py
===============
Endpoints d'administration pour la gestion des utilisateurs.
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.modules.users.schemas.responses import MessageResponse, PaginatedResponse
from app.modules.users.routes.dependencies import (
    get_db,
    get_current_superadmin,
    get_user_service,
    get_audit_service,
)
from app.modules.users.models import User
from app.modules.users.utils.helpers import paginate_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["Admin - Users"])


@router.get("/", response_model=dict)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    role: str = Query(None),
    plan: str = Query(None),
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Liste les utilisateurs avec filtres et pagination."""
    query = db.query(User).filter(User.is_deleted == False)

    if search:
        query = query.filter(
            User.email.ilike(f"%{search}%")
            | User.prenom.ilike(f"%{search}%")
        )
    if role:
        query = query.filter(User.role == role)
    if plan:
        query = query.filter(User.plan_effectif == plan)

    query = query.order_by(User.created_at.desc())
    items, total, pg, pp, total_pages = paginate_query(query, page, per_page)

    return {
        "items": [u.serialize_minimal() for u in items],
        "total": total,
        "page": pg,
        "per_page": pp,
        "total_pages": total_pages,
    }


@router.get("/{user_id}", response_model=dict)
async def get_user_detail(
    user_id: str,
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Détail complet d'un utilisateur."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"error": "USER_NOT_FOUND"}
    return user.serialize_minimal()


@router.put("/{user_id}/role", response_model=MessageResponse)
async def update_user_role(
    user_id: str,
    role: str = Query(..., regex="^(student|admin|superadmin)$"),
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Modifie le rôle d'un utilisateur."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return MessageResponse(message="Utilisateur non trouvé", code="USER_NOT_FOUND")

    user.role = role
    db.commit()
    return MessageResponse(message=f"Rôle mis à jour: {role}", code="ROLE_UPDATED")


@router.put("/{user_id}/plan", response_model=MessageResponse)
async def update_user_plan(
    user_id: str,
    plan: str = Query(...),
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Modifie le plan d'un utilisateur."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return MessageResponse(message="Utilisateur non trouvé", code="USER_NOT_FOUND")

    user.plan_effectif = plan
    db.commit()
    return MessageResponse(message=f"Plan mis à jour: {plan}", code="PLAN_UPDATED")


@router.post("/{user_id}/deactivate", response_model=MessageResponse)
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Désactive un utilisateur (soft)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return MessageResponse(message="Utilisateur non trouvé", code="USER_NOT_FOUND")

    user.is_active = False
    db.commit()
    return MessageResponse(message="Utilisateur désactivé", code="USER_DEACTIVATED")


@router.post("/{user_id}/reactivate", response_model=MessageResponse)
async def reactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Réactive un utilisateur désactivé."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return MessageResponse(message="Utilisateur non trouvé", code="USER_NOT_FOUND")

    user.is_active = True
    db.commit()
    return MessageResponse(message="Utilisateur réactivé", code="USER_REACTIVATED")


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """Supprime logiquement un utilisateur (RGPD)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return MessageResponse(message="Utilisateur non trouvé", code="USER_NOT_FOUND")

    user.soft_delete()
    db.commit()
    return MessageResponse(message="Utilisateur supprimé", code="USER_DELETED")


@router.get("/audit/logs", response_model=dict)
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    severity: str = Query(None),
    current_user: User = Depends(get_current_superadmin),
    audit_service=Depends(get_audit_service),
):
    """Consulte les logs d'audit (superadmin uniquement)."""
    logs = audit_service.get_recent_audit_events(limit=limit, severity=severity)
    return {"logs": logs, "total": len(logs)}
