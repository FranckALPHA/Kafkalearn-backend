"""
routes/admin_notifications.py
===============================
Admin-facing notification endpoints.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.modules.notifications.routes.dependencies import (
    get_db,
    get_current_admin,
    get_analytics_service,
    get_notification_service,
)
from app.modules.users.models import User
from app.modules.notifications.models import NotificationLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"])


class SendTopicRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1, max_length=1000)
    type_notif: str = Field(default="annonce", max_length=30)
    data: Optional[dict] = None


@router.get("/stats")
async def get_admin_stats(
    period: str = Query("7d", pattern=r"^\d+d$"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Return notification statistics (admin only)."""
    analytics = get_analytics_service(db=db)
    return analytics.get_stats(period=period)


@router.post("/send-topic")
async def send_to_topic(
    body: SendTopicRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Send a notification to an FCM topic (admin only)."""
    notif_service = get_notification_service(db=db)
    result = notif_service.send_to_topic(
        topic=body.topic,
        title=body.title,
        body=body.body,
        type_notif=body.type_notif,
        data=body.data,
    )
    return {"status": "ok", **result}


@router.get("/unread-counts")
async def get_unread_counts(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Return unread notification counts per user (admin only)."""
    rows = (
        db.query(
            NotificationLog.user_id,
            sa_func.count(NotificationLog.id).label("unread_count"),
        )
        .filter(NotificationLog.is_read == False)  # noqa: E712
        .group_by(NotificationLog.user_id)
        .all()
    )
    return {
        "counts": [
            {"user_id": str(row.user_id), "unread": row.unread_count}
            for row in rows
        ],
        "total_users_with_unread": len(rows),
    }
