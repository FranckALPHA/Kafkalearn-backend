"""
routes/user_notifications.py
=============================
User-facing notification endpoints.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.modules.notifications.schemas.requests import RegisterDeviceRequest, UpdatePreferencesRequest
from app.modules.notifications.schemas.responses import NotificationHistoryResponse, PreferencesResponse
from app.modules.notifications.models import Device, NotificationLog, NotificationPreference
from app.modules.notifications.routes.dependencies import (
    get_db,
    get_current_user,
    get_notification_service,
    get_scheduler_service,
    get_rate_limiter_dependency,
    notif_rate_limiter,
    register_rate_limiter,
)
from app.modules.users.models import User
from app.modules.users.utils.rate_limiter import get_rate_limiter_dependency as get_rl_dep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/me/history", response_model=NotificationHistoryResponse)
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rl_dep(notif_rate_limiter)),
):
    """Return notification history for the authenticated user."""
    total = (
        db.query(NotificationLog)
        .filter(NotificationLog.user_id == current_user.id)
        .count()
    )
    nb_non_lues = (
        db.query(NotificationLog)
        .filter(NotificationLog.user_id == current_user.id, NotificationLog.is_read == False)  # noqa: E712
        .count()
    )
    logs = (
        db.query(NotificationLog)
        .filter(NotificationLog.user_id == current_user.id)
        .order_by(NotificationLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return NotificationHistoryResponse(
        total=total,
        nb_non_lues=nb_non_lues,
        notifications=[log.serialize_for_history() for log in logs],
    )


@router.put("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rl_dep(notif_rate_limiter)),
):
    """Mark a single notification as read."""
    notif_service = get_notification_service(db=db)
    success = notif_service.mark_as_read(notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="NOTIFICATION_NOT_FOUND")
    return {"status": "ok", "message": "Notification marked as read"}


@router.put("/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rl_dep(notif_rate_limiter)),
):
    """Mark all notifications as read."""
    notif_service = get_notification_service(db=db)
    count = notif_service.mark_all_as_read(current_user.id)
    return {"status": "ok", "count": count}


@router.get("/me/preferences", response_model=PreferencesResponse)
async def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rl_dep(notif_rate_limiter)),
):
    """Return the user's notification preferences."""
    prefs = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == current_user.id)
        .first()
    )
    if prefs is None:
        # Create defaults
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return PreferencesResponse(**prefs.serialize())


@router.patch("/me/preferences")
async def update_preferences(
    body: UpdatePreferencesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rl_dep(notif_rate_limiter)),
):
    """Update the user's notification preferences."""
    prefs = (
        db.query(NotificationPreference)
        .filter(NotificationPreference.user_id == current_user.id)
        .first()
    )
    if prefs is None:
        prefs = NotificationPreference(user_id=current_user.id)
        db.add(prefs)

    update_fields = body.model_dump(exclude_none=True)
    for key, value in update_fields.items():
        if key in ("heure_silencieuse_debut", "heure_silencieuse_fin") and value is not None:
            from datetime import time as dt_time
            parts = str(value).split(":")
            setattr(prefs, key, dt_time(int(parts[0]), int(parts[1])))
        else:
            setattr(prefs, key, value)

    db.commit()
    db.refresh(prefs)
    return PreferencesResponse(**prefs.serialize())


@router.post("/register")
async def register_device(
    body: RegisterDeviceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _rl=Depends(get_rl_dep(register_rate_limiter)),
):
    """Register or update a device FCM token."""
    # Check if token already exists
    existing = db.query(Device).filter(Device.fcm_token == body.fcm_token).first()
    if existing:
        existing.user_id = current_user.id
        existing.platform = body.platform
        existing.app_version = body.app_version
        existing.device_model = body.device_model
        existing.is_active = True
        existing.last_seen = datetime.now()
        existing.notifs_enabled = True
        # Update topics
        existing.topics_souscrits = existing.serialize_for_topics()
        db.commit()
        db.refresh(existing)
        return {"status": "ok", "device_id": existing.id, "message": "Device updated"}

    # Create new device
    device = Device(
        user_id=current_user.id,
        fcm_token=body.fcm_token,
        platform=body.platform,
        app_version=body.app_version,
        device_model=body.device_model,
        classe=current_user.classe,
        serie=current_user.serie,
        langue=current_user.langue,
    )
    device.topics_souscrits = device.serialize_for_topics()
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"status": "ok", "device_id": device.id, "message": "Device registered"}
