"""
jobs/tasks.py
=============
Celery tasks for referral operations: notifications, reward checks, sync.
"""
import logging
from datetime import datetime, timedelta

from app.modules.referral.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    """Create a new DB session for use inside a Celery task."""
    from app.core.database import SessionLocal
    return SessionLocal()


def _get_redis():
    """Get Redis client for use inside a Celery task."""
    try:
        from app.modules.core.redis_client import redis_client
        return redis_client
    except Exception:
        return None


# ─── Notification tasks ─────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def notify_referral_active_task(self, referrer_id: str, referee_prenom: str):
    """Notify a referrer that their referee has become active."""
    try:
        # Try to import NotificationService; fall back gracefully
        try:
            from app.modules.notifications.services.notification_service import NotificationService
            db = _get_db()
            service = NotificationService(db=db)
            service.send_to_user(
                user_id=referrer_id,
                title="Votre filleul est actif!",
                body=f"{referee_prenom} a rejoint KafkaLearn et est maintenant actif. Continuez a parrainer pour debloquer des recompenses!",
                type_notif="referral_actif",
                data={"referee_prenom": referee_prenom},
            )
            db.close()
        except ImportError:
            logger.warning(
                "NotificationService not available. Referral active notification for %s about %s",
                referrer_id,
                referee_prenom,
            )
        return {"success": True, "referrer_id": referrer_id}
    except Exception as exc:
        logger.exception("Error in notify_referral_active_task")
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def notify_referral_reward_task(self, referrer_id: str, plan: str, cycle: int):
    """Notify a referrer that they received a reward."""
    try:
        try:
            from app.modules.notifications.services.notification_service import NotificationService
            db = _get_db()
            service = NotificationService(db=db)
            service.send_to_user(
                user_id=referrer_id,
                title="Recompense de parrainage!",
                body=f"Felicitations! Vous avez atteint le palier de {cycle} filleuls actifs. Votre plan est maintenant upgrade vers {plan} pour 30 jours!",
                type_notif="referral_reward",
                data={"plan": plan, "cycle": cycle},
            )
            db.close()
        except ImportError:
            logger.warning(
                "NotificationService not available. Referral reward notification for %s: plan=%s, cycle=%d",
                referrer_id,
                plan,
                cycle,
            )
        return {"success": True, "referrer_id": referrer_id}
    except Exception as exc:
        logger.exception("Error in notify_referral_reward_task")
        raise self.retry(exc=exc)


# ─── Maintenance tasks ──────────────────────────────────────────────

@celery_app.task
def check_expired_rewards_task():
    """Check for expired rewards and revert plans to base."""
    db = _get_db()
    try:
        from app.modules.referral.models import ReferralReward
        from app.modules.users.models import User

        expired_rewards = (
            db.query(ReferralReward)
            .filter(
                ReferralReward.expiration_at < datetime.utcnow(),
                ReferralReward.expiration_at > datetime.utcnow() - timedelta(hours=2),
            )
            .all()
        )

        reverted_count = 0
        for reward in expired_rewards:
            user = db.query(User).filter(User.id == reward.user_id).first()
            if user:
                # Only revert if the current plan matches the rewarded plan
                if user.plan_effectif == reward.plan_apres:
                    user.plan_effectif = reward.plan_avant
                    user.plan_expiration_at = None
                    reverted_count += 1

        db.commit()
        logger.info(
            "check_expired_rewards_task: reverted %d expired rewards.", reverted_count
        )
    except Exception:
        logger.exception("Error in check_expired_rewards_task")
        db.rollback()
    finally:
        db.close()


@celery_app.task
def sync_active_referees_task():
    """Safety net: check inactive referees >7 days and activate if they have search/payment activity."""
    db = _get_db()
    try:
        from app.modules.referral.models import ReferralActivity
        from app.modules.users.models import User

        # Find inactive referrals older than 7 days
        cutoff = datetime.utcnow() - timedelta(days=7)
        inactive_referees = (
            db.query(ReferralActivity)
            .filter(
                ReferralActivity.is_active == False,
                ReferralActivity.date_ref < cutoff,
            )
            .all()
        )

        activated_count = 0
        for activity in inactive_referees:
            referee = db.query(User).filter(User.id == activity.referee_id).first()
            if not referee:
                continue

            # Check if they have search activity
            has_search = False
            has_payment = False
            try:
                from app.modules.search.models import SearchActivity
                search_count = (
                    db.query(SearchActivity)
                    .filter(SearchActivity.user_id == referee.id)
                    .count()
                )
                has_search = search_count > 0
            except Exception:
                pass

            try:
                from app.modules.users.models import UserActivity
                payment_activities = (
                    db.query(UserActivity)
                    .filter(
                        UserActivity.user_id == referee.id,
                        UserActivity.activity_type == "payment",
                    )
                    .count()
                )
                has_payment = payment_activities > 0
            except Exception:
                pass

            if has_search or has_payment:
                activity.is_active = True
                activity.date_activation = datetime.utcnow()
                activated_count += 1

                # Also check reward for referrer
                try:
                    from app.modules.referral.services.referral_service import ReferralService
                    referral_svc = ReferralService(db=db)
                    referral_svc.verifier_et_appliquer_recompense(str(activity.referrer_id))
                except Exception:
                    logger.warning(
                        "Failed to check reward for referrer %s after sync activation",
                        activity.referrer_id,
                    )

        db.commit()
        logger.info(
            "sync_active_referees_task: activated %d inactive referees.", activated_count
        )
    except Exception:
        logger.exception("Error in sync_active_referees_task")
        db.rollback()
    finally:
        db.close()
