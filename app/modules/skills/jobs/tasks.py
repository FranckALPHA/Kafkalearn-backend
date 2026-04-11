from .celery_app import celery_app
from sqlalchemy.orm import sessionmaker
from database import engine
import logging

logger = logging.getLogger(__name__)
SessionLocal = sessionmaker(bind=engine)

# ─── Tâches de génération PDF (lourdes) ─────────────────────────
@celery_app.task(name="skills.tasks.generate_fiche_pdf", queue="heavy")
def generate_fiche_pdf_task(user_id: str, message_id: int, contenu_markdown: str, metadata: dict):
    """
    Génération asynchrone d'une fiche PDF via ReportLab.
    Utilisée quand la génération synchrone dépasse le timeout.
    """
    db = SessionLocal()
    try:
        from utils.pdf_generator import PDFGenerator
        from modules.skills.services.chat_service import ChatService
        
        # Génération PDF
        pdf_bytes = PDFGenerator().generate_fiche_pdf(
            titre=metadata["titre"],
            metadata=metadata,
            contenu_markdown=contenu_markdown
        )
        
        # Upload vers stockage (S3-compatible ou local)
        from utils.storage import upload_file
        file_url = upload_file(
            file_bytes=pdf_bytes,
            filename=f"fiche_{metadata.get('uuid')}.pdf",
            content_type="application/pdf",
            folder="fiches"
        )
        
        # Mise à jour du message avec l'URL
        message = db.query(ChatMessage).get(message_id)
        if message:
            message.file_url = file_url
            message.output_type = "pdf"
            db.commit()
        
        # Notification utilisateur
        from modules.notifications.services.notification_service import NotificationService
        NotificationService(db).send_to_user(
            user_id=user_id,
            title="📄 Ta fiche est prête !",
            body=f"{metadata['titre']} est disponible dans ta bibliothèque.",
            data={"type": "skill_ready", "file_url": file_url, "asset_type": "FICHE"}
        )
        
        return {"success": True, "file_url": file_url}
        
    except Exception as e:
        logger.error(f"Erreur génération PDF user {user_id}: {e}")
        # Mise à jour message avec erreur
        try:
            message = db.query(ChatMessage).get(message_id)
            if message:
                message.erreur_code = "PDF_GENERATION_FAILED"
                db.commit()
        except:
            pass
        raise generate_fiche_pdf_task.retry(exc=e, countdown=300, max_retries=2)
    finally:
        db.close()

# ─── Tâches d'enrichissement profil ────────────────────────────
@celery_app.task(name="skills.tasks.enrich_profile_after_skill", queue="default")
def enrich_profile_after_skill_task(user_id: str, skill_type: str, matiere: str, succes: bool, score: float = None):
    """
    Enrichit le profil apprenant après une exécution de skill.
    """
    db = SessionLocal()
    try:
        from modules.users.services.learning_profile_service import LearningProfileService
        LearningProfileService(db).enregistrer_skill_usage(
            user_id=user_id,
            skill_type=skill_type,
            matiere=matiere,
            succes=succes
        )
        
        # Si quiz avec score → mise à jour score par matière
        if skill_type == "quiz" and score is not None and matiere:
            LearningProfileService(db).enregistrer_score_quiz(
                user_id=user_id,
                matiere=matiere,
                score=score
            )
    except Exception as e:
        logger.error(f"Erreur enrich_profile user {user_id}: {e}")
        raise enrich_profile_after_skill_task.retry(exc=e, countdown=60)
    finally:
        db.close()

# ─── Tâches de maintenance ─────────────────────────────────────
@celery_app.task(name="skills.tasks.cleanup_old_sessions", queue="cron")
def cleanup_old_sessions(days_to_keep_archived: int = 90, days_to_keep_active: int = 365):
    """
    Supprime les sessions anciennes (RGPD + performance).
    Conserve les sessions avec note utilisateur pour analytics.
    """
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta
        
        # Sessions archivées anciennes
        archived_cutoff = datetime.utcnow() - timedelta(days=days_to_keep_archived)
        db.query(ChatSession).filter(
            ChatSession.is_archived == True,
            ChatSession.updated_at < archived_cutoff,
            ChatSession.note_utilisateur.is_(None)
        ).delete(synchronize_session=False)
        
        # Sessions actives très anciennes (inactives > 1 an)
        active_cutoff = datetime.utcnow() - timedelta(days=days_to_keep_active)
        db.query(ChatSession).filter(
            ChatSession.is_archived == False,
            ChatSession.updated_at < active_cutoff,
            ChatSession.nb_messages == 0,  # jamais utilisées
            ChatSession.note_utilisateur.is_(None)
        ).delete(synchronize_session=False)
        
        db.commit()
        logger.info("Cleanup sessions terminé")
        
    except Exception as e:
        logger.error(f"Erreur cleanup sessions: {e}")
        db.rollback()
        raise
    finally:
        db.close()