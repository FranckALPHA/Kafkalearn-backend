"""
jobs/tasks.py
=============
Tâches Celery asynchrones pour le module payment.
"""
import logging
from datetime import datetime, timedelta

from app.modules.payment.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    """Crée une session DB dédiée pour les tâches Celery."""
    from app.core.database import SessionLocal
    engine_session = SessionLocal
    return engine_session()


# ─── Tâches de notification et validation ──────────────────────

@celery_app.task(name="payment.tasks.notify_payment_complete", bind=True, max_retries=3)
def notify_payment_complete_task(self, user_id: str, plan_id: str):
    """Envoie une notification de confirmation de paiement a l'utilisateur."""
    try:
        from app.modules.notifications.services.notification_service import NotificationService
        db = _get_db()
        try:
            svc = NotificationService(db=db)
            plan_names = {
                "access": "Accès",
                "premium": "Premium",
                "pro": "Pro",
                "unlimited": "Illimité",
                "school": "École",
            }
            plan_name = plan_names.get(plan_id, plan_id)
            svc.envoyer_template(
                user_id=user_id,
                template_type="payment_confirm",
                params={"plan": plan_name},
                type_notif="payment_confirm",
            )
        finally:
            db.close()
    except ImportError:
        logger.warning("NotificationService non disponible, notification sautée")
    except Exception as e:
        logger.error(f"Erreur notification paiement user {user_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name="payment.tasks.validate_subscription", bind=True, max_retries=3)
def validate_subscription_task(self, transaction_id: str):
    """Valide l'abonnement apres paiement confirme."""
    db = _get_db()
    try:
        from app.modules.payment.models import Transaction
        from app.modules.payment.services import PaymentService

        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            logger.error(f"Transaction {transaction_id} introuvable")
            return

        payment_service = PaymentService(db=db)
        import asyncio
        asyncio.run(payment_service.valider_abonnement(transaction))

        # Envoyer la notification
        notify_payment_complete_task.delay(str(transaction.user_id), transaction.plan_id)
    except Exception as e:
        logger.error(f"Erreur validation abonnement tx {transaction_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()


# ─── Tâches cron (Celery Beat) ────────────────────────────────

@celery_app.task(name="payment.tasks.expire_individual_plans", queue="cron")
def expire_individual_plans_task():
    """Verifie les plans expires et retrograde les utilisateurs en freemium."""
    db = _get_db()
    try:
        from app.modules.users.models import User
        from app.modules.users.models.mixins import func as sa_func_now

        now = datetime.utcnow()

        expired_users = (
            db.query(User)
            .filter(
                User.plan_expiration_at.isnot(None),
                User.plan_expiration_at < now,
                User.plan_effectif != "freemium",
                User.is_active == True,
                User.is_deleted == False,
            )
            .all()
        )

        for user in expired_users:
            try:
                user.plan_base = "freemium"
                user.plan_effectif = "freemium"
                db.commit()
                logger.info(f"Plan expire pour user {user.id}, retrograde en freemium")

                # Notifier l'utilisateur
                try:
                    from app.modules.notifications.services.notification_service import NotificationService
                    notif_svc = NotificationService(db=db)
                    notif_svc.envoyer_template(
                        user_id=str(user.id),
                        template_type="plan_expired",
                        params={"plan": user.plan_effectif},
                        type_notif="payment_confirm",
                    )
                except ImportError:
                    pass
            except Exception as e:
                logger.error(f"Erreur expiration plan user {user.id}: {e}")
                db.rollback()
                continue
    except Exception as e:
        logger.error(f"Erreur expire_individual_plans: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="payment.tasks.detect_churn", queue="cron")
def detect_churn_task():
    """Detecte les utilisateurs qui n'ont pas renouvele leur abonnement."""
    db = _get_db()
    try:
        from app.modules.users.models import User

        # Users dont le plan a expire recemment sans renouvellement
        cutoff = datetime.utcnow() - timedelta(days=7)

        churned_users = (
            db.query(User)
            .filter(
                User.plan_effectif == "freemium",
                User.plan_base != "freemium",
                User.derniere_activite_at >= cutoff,
                User.is_active == True,
                User.is_deleted == False,
            )
            .all()
        )

        for user in churned_users:
            try:
                logger.info(f"Churn detecte pour user {user.id} ({user.email})")

                # Envoyer notification de relance
                try:
                    from app.modules.notifications.services.notification_service import NotificationService
                    notif_svc = NotificationService(db=db)
                    notif_svc.envoyer_template(
                        user_id=str(user.id),
                        template_type="churn_relance",
                        params={"prenom": user.prenom or "Utilisateur"},
                        type_notif="payment_confirm",
                    )
                except ImportError:
                    pass
            except Exception as e:
                logger.error(f"Erreur churn detection user {user.id}: {e}")
                continue
    except Exception as e:
        logger.error(f"Erreur detect_churn: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="payment.tasks.calculate_daily_mrr", queue="cron")
def calculate_daily_mrr_task():
    """Calcule et cache le MRR quotidien."""
    db = _get_db()
    try:
        from app.modules.payment.services import PaymentAnalyticsService

        analytics_svc = PaymentAnalyticsService(db=db)
        import asyncio
        mrr_data = asyncio.run(analytics_svc.calculer_mrr())

        logger.info(f"MRR calcule: total={mrr_data.get('total_mrr', 0)}")
        return mrr_data
    except Exception as e:
        logger.error(f"Erreur calcul MRR: {e}")
        db.rollback()
    finally:
        db.close()
