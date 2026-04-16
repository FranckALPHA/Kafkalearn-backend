import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.epreuves.routes.dependencies import (
    get_db, get_current_user, get_document_service, get_stats_service, get_filter_cache_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/epreuves", tags=["Admin - Epreuves"])


def _check_admin(current_user: User):
    """Check if user is admin or superadmin."""
    if current_user.role not in ("admin", "superadmin"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")

@router.get("/stats")
async def get_global_stats(
    current_user: User = Depends(get_current_user),
    stats_service=Depends(get_stats_service),
):
    _check_admin(current_user)
    return stats_service.get_stats_globales()


@router.post("/ingest/{doc_id}")
async def trigger_ingestion(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    doc_service=Depends(get_document_service),
):
    _check_admin(current_user)

    doc = await doc_service.recuperer_par_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")

    try:
        from app.modules.epreuves.jobs.tasks import run_ingestion
        run_ingestion.delay(doc_id=doc_id)
        return {"message": "Ingestion lancée", "document_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"INGESTION_ERROR: {str(e)}")


@router.post("/invalidate-cache")
async def invalidate_filter_cache(
    current_user: User = Depends(get_current_user),
    filter_service=Depends(get_filter_cache_service),
):
    _check_admin(current_user)
    filter_service.invalider_et_reconstruire()
    return {"message": "Cache des filtres invalidé"}


@router.get("/pending-ingestion")
async def get_pending_documents(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_admin(current_user)

    from app.modules.epreuves.models import Document
    pending = db.query(Document).filter(
        Document.ingest_status == "pending"
    ).order_by(Document.created_at.desc()).limit(limit).all()

    return {"documents": [d.serialize_list_item() for d in pending], "total": len(pending)}
