import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.user_documents.routes.dependencies import (
    get_db,
    get_current_user,
    get_extractor_service,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/user-documents", tags=["Admin - User Documents"])


def _check_admin(current_user: User):
    """Check if user is admin or superadmin."""
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="INSUFFICIENT_PERMISSIONS")


@router.get("/stats")
async def get_global_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get global document statistics (SuperAdmin only)."""
    _check_admin(current_user)

    from sqlalchemy import func
    from app.modules.user_documents.models import UserDocument

    total_docs = db.query(func.count(UserDocument.id)).scalar() or 0
    total_size = db.query(func.coalesce(func.sum(UserDocument.poids_octets), 0)).scalar() or 0
    pending_extraction = (
        db.query(func.count(UserDocument.id))
        .filter(UserDocument.extraction_status == "pending")
        .scalar()
        or 0
    )
    failed_extraction = (
        db.query(func.count(UserDocument.id))
        .filter(UserDocument.extraction_status == "failed")
        .scalar()
        or 0
    )
    vectorized = (
        db.query(func.count(UserDocument.id))
        .filter(UserDocument.is_vectorized == True)
        .scalar()
        or 0
    )

    return {
        "total_documents": total_docs,
        "espace_total_bytes": total_size,
        "pending_extraction": pending_extraction,
        "failed_extraction": failed_extraction,
        "vectorized": vectorized,
    }


@router.post("/retry-extractions")
async def retry_failed_extractions(
    max_docs: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    extractor_service=Depends(get_extractor_service),
):
    """Re-process failed extractions (SuperAdmin only)."""
    _check_admin(current_user)

    result = await extractor_service.retraiter_echecs(max_docs=max_docs)
    return result
