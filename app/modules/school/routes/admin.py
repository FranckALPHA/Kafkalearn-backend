"""
routes/admin.py
===============
Endpoints SuperAdmin pour la gestion globale des écoles.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from app.modules.school.routes.dependencies import (
    get_current_user,
    get_db,
    get_school_service,
    get_expiration_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/school", tags=["Admin School"])


def require_superadmin(current_user=Depends(get_current_user)):
    if getattr(current_user, "role", None) != "superadmin":
        raise HTTPException(status_code=403, detail="SUPERADMIN_REQUIRED")
    return current_user


@router.get("/")
async def list_schools(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    current_user=Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    """Lister toutes les écoles (SuperAdmin uniquement, avec pagination)."""
    from app.modules.school.models import School
    from sqlalchemy import or_

    q = db.query(School)
    if search:
        q = q.filter(
            or_(
                School.nom.ilike(f"%{search}%"),
                School.id.ilike(f"%{search}%"),
                School.ville.ilike(f"%{search}%"),
            )
        )

    total = q.count()
    schools = q.order_by(School.date_creation.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "schools": [
            {
                "id": s.id,
                "nom": s.nom,
                "ville": s.ville,
                "region": s.region,
                "nb_membres": s.nb_membres_actifs,
                "nb_eleves_max": s.nb_eleves_max,
                "is_active": s.is_active,
                "jours_restants": s.jours_restants,
                "date_expiration": s.date_expiration.isoformat() if s.date_expiration else None,
                "admin_id": s.admin_id,
            }
            for s in schools
        ],
    }


@router.get("/stats")
async def get_school_stats(
    current_user=Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    """Statistiques globales des écoles (SuperAdmin uniquement)."""
    from app.modules.school.models import School, SchoolMember

    total_ecoles = db.query(School).count()
    ecoles_actives = db.query(School).filter(School.is_active == True).count()
    ecoles_expired = db.query(School).filter(School.is_active == False).count()
    total_membres = db.query(SchoolMember).filter(SchoolMember.is_active == True).count()

    # Écoles expirant dans les 7 prochains jours
    now = datetime.now(timezone.utc)
    week_from_now = now + timedelta(days=7)
    ecoles_exp_bientot = (
        db.query(School)
        .filter(
            School.is_active == True,
            School.date_expiration.between(now, week_from_now),
        )
        .count()
    )

    return {
        "total_ecoles": total_ecoles,
        "ecoles_actives": ecoles_actives,
        "ecoles_expired": ecoles_expired,
        "total_membres": total_membres,
        "ecoles_exp_bientot_7j": ecoles_exp_bientot,
    }


@router.get("/{school_id}")
async def get_school_detail(
    school_id: str,
    current_user=Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    """Détails d'une école (SuperAdmin uniquement)."""
    from app.modules.school.models import School

    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="SCHOOL_NOT_FOUND")

    details = school.serialize_dashboard(is_admin=True)
    details["nb_membres_actifs"] = school.nb_membres_actifs
    return details


@router.post("/{school_id}/reactivate")
async def reactivate_school(
    school_id: str,
    days: int = Query(30, ge=1, le=365),
    current_user=Depends(require_superadmin),
    db: Session = Depends(get_db),
    expiration_service=Depends(get_expiration_service),
):
    """Réactiver manuellement une école expirée (SuperAdmin uniquement)."""
    from app.modules.school.models import School

    school = db.query(School).filter(School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="SCHOOL_NOT_FOUND")

    await expiration_service.reactiver_ecole(
        school_id=school_id,
        nouvelle_expiration=datetime.now(timezone.utc) + timedelta(days=days),
    )

    return {"message": f"École {school.nom} réactivée pour {days} jours."}
