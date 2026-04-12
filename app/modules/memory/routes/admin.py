"""
routes/admin.py
===============
Admin routes for memory module (SuperAdmin only).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.modules.memory.routes.dependencies import (
    get_db,
    get_current_user,
    get_generator_service,
)
from app.modules.memory.services.memory_generator_service import MemoryGeneratorService
from app.modules.memory.models import MemorySection, MemoryItem, UserSectionProgress, MemoryItemAttempt
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/memory", tags=["Memory Admin"])


def _require_superadmin(user: User):
    """Ensure the current user is a SuperAdmin."""
    if user.role != "superadmin":
        raise HTTPException(status_code=403, detail="SUPERADMIN_REQUIRED")


# -------------------------------------------------------------------
# GET /admin/memory/stats — global memory stats (SuperAdmin only)
# -------------------------------------------------------------------
@router.get("/stats")
async def get_global_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get global memory statistics across all users."""
    _require_superadmin(user)

    total_sections = db.query(MemorySection).count()
    total_items = db.query(MemoryItem).count()
    total_attempts = db.query(MemoryItemAttempt).count()
    total_user_progress_records = db.query(UserSectionProgress).count()

    # Average accuracy across all attempts
    if total_attempts > 0:
        correct_count = (
            db.query(MemoryItemAttempt)
            .filter(MemoryItemAttempt.est_correct.is_(True))
            .count()
        )
        accuracy = correct_count / total_attempts
    else:
        accuracy = 0.0

    # Sections by generation status
    sections_by_status = {}
    for status in ["pending", "generating", "complete", "partial", "failed"]:
        count = (
            db.query(MemorySection)
            .filter(MemorySection.generation_status == status)
            .count()
        )
        sections_by_status[status] = count

    # Unique users with memory activity
    active_users = (
        db.query(MemoryItemAttempt.user_id)
        .distinct()
        .count()
    )

    return {
        "total_sections": total_sections,
        "total_items": total_items,
        "total_attempts": total_attempts,
        "total_progress_records": total_user_progress_records,
        "accuracy": round(accuracy, 4),
        "sections_by_status": sections_by_status,
        "active_users": active_users,
    }


# -------------------------------------------------------------------
# POST /admin/memory/regenerate/{section_id} — regenerate section (SuperAdmin only)
# -------------------------------------------------------------------
@router.post("/regenerate/{section_id}")
async def regenerate_section(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    generator_service: MemoryGeneratorService = Depends(get_generator_service),
):
    """Trigger regeneration of a memory section."""
    _require_superadmin(user)

    section = db.query(MemorySection).filter(MemorySection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="SECTION_NOT_FOUND")

    result = await generator_service.regenerer_section(section_id=section_id, force=True)

    return {
        "section_id": section_id,
        "status": result.get("status", result.get("nb_items_generes", 0)),
        "message": result.get("message", f"Regenerated {result.get('nb_items_generes', 0)} items"),
    }
