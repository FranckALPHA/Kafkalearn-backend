"""
jobs/tasks.py
=============
Tâches Celery asynchrones pour le module users.
"""
import logging
from datetime import datetime, timedelta

from app.modules.users.jobs.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import DATABASE_URL

logger = logging.getLogger(__name__)


def _get_db():
    """Crée une session DB dédiée pour les tâches Celery."""
    engine_session = SessionLocal
    return engine_session()


# ─── Tâches légères ───────────────────────────────────────────────

@celery_app.task(name="users.tasks.update_streak", queue="default", bind=True, max_retries=3)
def update_streak_task(self, user_id: str):
    """Met à jour le streak de connexion."""
    db = _get_db()
    try:
        from app.modules.users.services.streak_service import StreakService
        StreakService(db).calculer_streak(user_id)
        db.commit()
    except Exception as e:
        logger.error(f"Erreur update_streak user {user_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(name="users.tasks.recalc_score", queue="default", bind=True, max_retries=3)
def recalc_score_task(self, user_id: str):
    """Recalcule le score global."""
    db = _get_db()
    try:
        from app.modules.users.services.score_global_service import ScoreGlobalService
        ScoreGlobalService(db).recalculer(user_id)
        db.commit()
    except Exception as e:
        logger.error(f"Erreur recalc_score user {user_id}: {e}")
        db.rollback()
        raise self.retry(exc=e, countdown=120)
    finally:
        db.close()


# ─── Tâches lourdes (I/O, LLM, PDF) ─────────────────────────────

@celery_app.task(name="users.tasks.send_otp_email", queue="emails", bind=True, max_retries=2)
def send_otp_email_task(self, user_id: str, email: str, prenom: str, otp_code: str, type: str):
    """Envoi d'email OTP via Brevo/SMTP."""
    try:
        from app.modules.users.services.mail_service import MailService
        MailService().envoyer_otp(email, prenom, otp_code, type)
    except Exception as e:
        logger.error(f"Échec envoi OTP user {user_id}: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task(name="users.tasks.generate_pdf_report", queue="heavy", bind=True, max_retries=2)
def generate_pdf_report_task(self, user_id: str, report_id: int, declencheur: str):
    """
    Génération complète d'un rapport cognitif PDF.
    1. Appel LLM pour le résumé narratif
    2. Génération PDF via ReportLab
    3. Stockage + notification
    """
    db = _get_db()
    try:
        from app.modules.users.services.profile_report_service import ProfileReportService
        report_service = ProfileReportService(db)

        # Appel LLM pour le résumé
        llm_summary = call_llm_for_summary_task.apply(args=[user_id], queue="llm").get(timeout=60)

        # Génération PDF (placeholder)
        pdf_bytes = b""  # TODO: Implement with ReportLab

        # Mise à jour du statut
        report_service.update_rapport_status(report_id, "completed", {
            "rapport_json": llm_summary,
            "completed_at": datetime.utcnow().isoformat(),
        })

        return {"report_id": report_id, "status": "completed"}

    except Exception as e:
        logger.error(f"Échec génération rapport {report_id} user {user_id}: {e}")
        db.rollback()
        try:
            from app.modules.users.services.profile_report_service import ProfileReportService
            ProfileReportService(db).update_rapport_status(report_id, "failed", {
                "error_message": str(e),
                "failed_at": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(name="users.tasks.call_llm_for_summary", queue="llm", bind=True, max_retries=3)
def call_llm_for_summary_task(self, user_id: str) -> dict:
    """Appel au LLM pour générer le résumé narratif."""
    try:
        # TODO: Implement actual LLM call
        return {
            "resume_narratif": f"Résumé généré pour l'utilisateur {user_id}",
            "recommandations": ["Continuer à pratiquer régulièrement"],
        }
    except Exception as e:
        logger.error(f"Erreur appel LLM user {user_id}: {e}")
        raise self.retry(exc=e, countdown=30)


# ─── Tâches cron (Celery Beat) ──────────────────────────────────

@celery_app.task(name="users.tasks.nightly_score_recalc", queue="cron")
def nightly_score_recalc():
    """Recalcule les scores pour tous les users actifs."""
    db = _get_db()
    try:
        from app.modules.users.models import User
        from app.modules.users.services.score_global_service import ScoreGlobalService

        users = db.query(User).filter(
            User.derniere_activite_at >= datetime.utcnow() - timedelta(days=30),
            User.is_deleted == False,
        ).yield_per(100)

        for user in users:
            try:
                ScoreGlobalService(db).recalculer(str(user.id))
                db.commit()
            except Exception as e:
                logger.error(f"Erreur batch score user {user.id}: {e}")
                db.rollback()
                continue
    finally:
        db.close()


@celery_app.task(name="users.tasks.morning_churn_detection", queue="cron")
def morning_churn_detection():
    """Détection des users à risque de churn."""
    db = _get_db()
    try:
        from app.modules.users.services.churn_detector_service import ChurnDetectorService
        ChurnDetectorService(db).detecter_et_alerter()
        db.commit()
    except Exception as e:
        logger.error(f"Erreur churn detection: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="users.tasks.cleanup_expired_tokens", queue="cron")
def cleanup_expired_tokens():
    """Supprime les refresh tokens expirés."""
    db = _get_db()
    try:
        from app.modules.users.models import RefreshToken
        from sqlalchemy import func

        deleted = db.query(RefreshToken).filter(
            RefreshToken.expires_at < func.now()
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"Nettoyage: {deleted} tokens expirés supprimés")
    except Exception as e:
        logger.error(f"Erreur cleanup tokens: {e}")
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="users.tasks.weekly_auto_reports", queue="cron")
def weekly_auto_reports():
    """Génère les rapports hebdomadaires automatiques."""
    db = _get_db()
    try:
        from app.modules.users.models import User
        from app.modules.users.services.profile_report_service import ProfileReportService

        # Users premium/pro avec activité cette semaine
        users = db.query(User).filter(
            User.plan_effectif.in_(["premium", "pro", "unlimited"]),
            User.derniere_activite_at >= datetime.utcnow() - timedelta(days=7),
            User.is_deleted == False,
        ).all()

        report_service = ProfileReportService(db)
        for user in users:
            try:
                report_service.generer_rapport_async(str(user.id), "weekly_auto")
            except Exception as e:
                logger.error(f"Erreur rapport weekly user {user.id}: {e}")
                continue
        db.commit()
    except Exception as e:
        logger.error(f"Erreur weekly reports: {e}")
        db.rollback()
    finally:
        db.close()
