from app.modules.school.jobs.celery_app import celery_app
from app.modules.school.models.school import School
from app.modules.school.models.user_school import UserSchool
from app.modules.school.services.expiration import SchoolExpirationService
from app.modules.school.services.engagement import SchoolEngagementService
from app.modules.school.services.quota import SchoolQuotaService

try:
    from app.modules.notifications.service import NotificationService
except ImportError:
    NotificationService = None


def _get_db():
    from app.core.database import SessionLocal
    return SessionLocal()


@celery_app.task(bind=True, name="school.tasks.send_school_invitation_email_task")
def send_school_invitation_email_task(self, user_id: int, school_name: str, invitation_code: str):
    db = _get_db()
    try:
        if NotificationService is None:
            return {"status": "skipped", "reason": "NotificationService not available"}
        from app.modules.users.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "error", "reason": "user_not_found"}
        notif = NotificationService(db)
        import asyncio
        asyncio.run(notif.send_email(
            to_email=user.email,
            subject=f"Bienvenue à {school_name}",
            template="school_invitation",
            context={"school_name": school_name, "invitation_code": invitation_code},
        ))
        return {"status": "ok"}
    finally:
        db.close()


@celery_app.task(bind=True, name="school.tasks.notify_expiration_alert_task")
def notify_expiration_alert_task(self, admin_id: int, school_name: str, jours_restants: int):
    db = _get_db()
    try:
        if NotificationService is None:
            return {"status": "skipped", "reason": "NotificationService not available"}
        notif = NotificationService(db)
        import asyncio
        asyncio.run(notif.send_to_user(
            user_id=admin_id,
            title=f"Expiration: {jours_restants} jours",
            content=f"Votre école {school_name} expire dans {jours_restants} jours.",
        ))
        return {"status": "ok"}
    finally:
        db.close()


@celery_app.task(bind=True, name="school.tasks.update_user_plan_batch_task")
def update_user_plan_batch_task(self, user_ids: list, plan: str, school_id: int = None):
    db = _get_db()
    try:
        from app.modules.users.models.user import User
        db.query(User).filter(User.id.in_(user_ids)).update(
            {User.plan_effectif: plan, User.school_id: school_id},
            synchronize_session=False,
        )
        db.commit()
        return {"status": "ok", "updated": len(user_ids)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="school.tasks.check_school_expirations_task")
def check_school_expirations_task(self):
    db = _get_db()
    try:
        service = SchoolExpirationService(db)
        result = service.verifier_expirations()
        return {"alerts_sent": result.get("alerts_sent", 0)}
    finally:
        db.close()


@celery_app.task(bind=True, name="school.tasks.expire_schools_task")
def expire_schools_task(self):
    db = _get_db()
    try:
        service = SchoolExpirationService(db)
        result = service.expirer_ecoles()
        return {"expired_count": result.get("expired_count", 0)}
    finally:
        db.close()


@celery_app.task(bind=True, name="school.tasks.calculate_engagement_task")
def calculate_engagement_task(self):
    db = _get_db()
    try:
        service = SchoolEngagementService(db)
        active_schools = db.query(School).filter(School.statut == "active").all()
        results = []
        for school in active_schools:
            result = service.calculer_engagement(school.id)
            results.append({"school_id": school.id, **result})
        return {"processed": len(results)}
    finally:
        db.close()


@celery_app.task(bind=True, name="school.tasks.consolidate_daily_quota_task")
def consolidate_daily_quota_task(self):
    from app.core.database import get_redis_client
    redis = get_redis_client()
    db = _get_db()
    try:
        service = SchoolQuotaService(db, redis)
        active_schools = db.query(School).filter(School.statut == "active").all()
        results = []
        for school in active_schools:
            result = service.consolider_quota_jour(school.id)
            results.append({"school_id": school.id, **result})
        return {"processed": len(results)}
    finally:
        db.close()
