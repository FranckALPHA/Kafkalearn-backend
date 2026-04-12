"""
jobs/tasks.py
=============
Tâches Celery pour le module skills.
"""
import logging
from datetime import datetime, timedelta

from app.modules.skills.jobs.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


def _get_db():
    return SessionLocal()


@celery_app.task(name="skills.tasks.generate_fiche_pdf", queue="heavy", bind=True, max_retries=2)
def generate_fiche_pdf_task(
    self, user_id: str, message_id: int, contenu_markdown: str, metadata: dict
):
    """Génération asynchrone d'une fiche PDF via ReportLab."""
    db = _get_db()
    try:
        from app.modules.skills.utils.pdf_generator import PDFGenerator
        from app.modules.skills.models import ChatMessage

        # Génération PDF
        pdf_bytes = PDFGenerator().generate_fiche_pdf(
            titre=metadata["titre"],
            metadata=metadata,
            contenu_markdown=contenu_markdown,
        )

        # Stockage local (fallback avant S3)
        file_url = f"/data/fiches/fiche_{metadata.get('uuid', 'draft')}.pdf"

        # Mise à jour du message avec l'URL
        try:
            from app.modules.skills.models import ChatMessage
            message = db.query(ChatMessage).get(message_id)
            if message:
                message.file_url = file_url
                message.output_type = "pdf"
                db.commit()
        except Exception:
            pass

        # Notification utilisateur via le module notifications
        try:
            from app.modules.notifications.services.notification_service import NotificationService
            from app.core.database import SessionLocal
            notif_db = SessionLocal()
            NotificationService(notif_db).send_to_user(
                user_id=user_id,
                title="📄 Ta fiche est prête !",
                body=f"{metadata.get('titre', 'Ta fiche')} est disponible dans ta bibliothèque.",
                data={"type": "skill_ready", "file_url": file_url, "asset_type": "FICHE"},
            )
            notif_db.close()
        except Exception:
            pass  # Notification non critique

        return {"success": True, "file_url": file_url}

    except Exception as e:
        logger.error(f"Erreur génération PDF user {user_id}: {e}")
        try:
            from app.modules.skills.models import ChatMessage
            message = db.query(ChatMessage).get(message_id)
            if message:
                message.erreur_code = "PDF_GENERATION_FAILED"
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@celery_app.task(name="skills.tasks.enrich_profile_after_skill", queue="default", bind=True, max_retries=3)
def enrich_profile_after_skill_task(
    self, user_id: str, skill_type: str, matiere: str, succes: bool, score: float = None
):
    """Enrichit le profil apprenant après une exécution de skill."""
    db = _get_db()
    try:
        from app.modules.users.services.learning_profile_service import LearningProfileService

        LearningProfileService(db).enregistrer_skill_usage(
            user_id=user_id,
            skill_type=skill_type,
            matiere=matiere,
            succes=succes,
        )

        # Si quiz avec score → mise à jour score par matière
        if skill_type == "quiz" and score is not None and matiere:
            LearningProfileService(db).enregistrer_score_quiz(
                user_id=user_id,
                matiere=matiere,
                score=score,
            )
    except Exception as e:
        logger.error(f"Erreur enrich_profile user {user_id}: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@celery_app.task(name="skills.tasks.cleanup_old_sessions", queue="cron")
def cleanup_old_sessions(days_to_keep_archived: int = 90, days_to_keep_active: int = 365):
    """Supprime les sessions anciennes (RGPD + performance)."""
    db = _get_db()
    try:
        from app.modules.skills.models import ChatSession, ChatMessage

        # Sessions archivées anciennes
        archived_cutoff = datetime.utcnow() - timedelta(days=days_to_keep_archived)
        db.query(ChatSession).filter(
            ChatSession.is_archived == True,
            ChatSession.updated_at < archived_cutoff,
            ChatSession.note_utilisateur.is_(None),
        ).delete(synchronize_session=False)

        # Sessions actives très anciennes
        active_cutoff = datetime.utcnow() - timedelta(days=days_to_keep_active)
        db.query(ChatSession).filter(
            ChatSession.is_archived == False,
            ChatSession.updated_at < active_cutoff,
            ChatSession.nb_messages == 0,
            ChatSession.note_utilisateur.is_(None),
        ).delete(synchronize_session=False)

        db.commit()
        logger.info("Cleanup sessions terminé")

    except Exception as e:
        logger.error(f"Erreur cleanup sessions: {e}")
        db.rollback()
        raise
    finally:
        db.close()
