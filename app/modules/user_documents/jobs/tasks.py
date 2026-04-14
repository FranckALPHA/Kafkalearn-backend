"""
jobs/tasks.py
=============
Tâches Celery asynchrones pour le module user_documents.
"""
import logging
from datetime import datetime, timedelta, timezone

from app.modules.user_documents.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    """Crée une session DB dédiée pour les tâches Celery."""
    from app.core.database import SessionLocal
    return SessionLocal()


@celery_app.task(name="user_documents.tasks.extract_document_text", queue="default", bind=True, max_retries=3)
def extract_document_text_task(self, document_id: int):
    """Extract text from a user document."""
    db = _get_db()
    try:
        from app.modules.user_documents.services.user_document_extractor import UserDocumentExtractorService
        service = UserDocumentExtractorService(db=db)
        result = service.extraire(document_id)
        logger.info("Extraction task completed for doc %s: %s", document_id, result.get("status"))
    except Exception as exc:
        logger.exception("Extraction task failed for doc %s", document_id)
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task(name="user_documents.tasks.vectorize_document", queue="default", bind=True, max_retries=3)
def vectorize_document_task(self, document_id: int):
    """Vectorize a document for semantic search.

    Implementation:
    1. Split extracted text into chunks
    2. Generate embeddings for each chunk using FastEmbed
    3. Store embeddings in user_document_chunks table
    """
    db = _get_db()
    try:
        from app.modules.user_documents.models import UserDocument, UserDocumentChunk
        from app.modules.core.config import settings
        from fastembed import TextEmbedding
        import textwrap

        doc = db.query(UserDocument).filter(UserDocument.id == document_id).first()
        if not doc:
            logger.error("Document %s not found for vectorization", document_id)
            return {"status": "error", "message": "DOCUMENT_NOT_FOUND"}

        if not doc.extracted_text:
            logger.warning("Document %s has no extracted text", document_id)
            doc.vectorization_status = "failed"
            db.commit()
            return {"status": "error", "message": "NO_EXTRACTED_TEXT"}

        # Mark as processing
        doc.vectorization_status = "processing"
        db.commit()

        # Chunking: split text into segments of ~500 tokens (~2000 chars)
        chunk_size = 2000
        text_chunks = textwrap.wrap(doc.extracted_text, width=chunk_size)

        if not text_chunks:
            logger.warning("Document %s produced no chunks", document_id)
            doc.vectorization_status = "failed"
            db.commit()
            return {"status": "error", "message": "EMPTY_TEXT"}

        # Generate embeddings using FastEmbed
        embedding_model = TextEmbedding(model_name=settings.EMBEDDING_MODEL)
        embeddings = list(embedding_model.embed(text_chunks))

        # Delete old chunks if re-vectorizing
        db.query(UserDocumentChunk).filter(
            UserDocumentChunk.document_id == document_id
        ).delete()

        # Store chunks with embeddings
        nb_chunks = 0
        for idx, (chunk_text, embedding) in enumerate(zip(text_chunks, embeddings)):
            chunk = UserDocumentChunk(
                document_id=document_id,
                user_id=doc.user_id,
                chunk_idx=idx,
                texte_chunk=chunk_text.strip(),
                is_embedded=True,
            )
            db.add(chunk)
            nb_chunks += 1

        # Update document
        doc.is_vectorized = True
        doc.vectorization_status = "complete"
        doc.nb_chunks = nb_chunks
        db.commit()

        # Notify user
        try:
            from app.modules.notifications.services.notification_service import NotificationService
            from app.core.database import SessionLocal
            notif_db = SessionLocal()
            NotificationService(notif_db).send_to_user(
                user_id=doc.user_id,
                title="Vectorisation terminee",
                body=f"Votre document '{doc.titre}' est maintenant pret pour la recherche semantique.",
                type_notif="document_vectorized",
            )
            notif_db.close()
        except ImportError:
            pass

        logger.info("Vectorization completed for doc %s: %d chunks", document_id, nb_chunks)
        return {"status": "complete", "document_id": document_id, "nb_chunks": nb_chunks}
    except Exception as exc:
        logger.exception("Vectorization task failed for doc %s", document_id)
        db.rollback()
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()


@celery_app.task(name="user_documents.tasks.cleanup_orphan_files", queue="cron")
def cleanup_orphan_files_task():
    """Remove physical files that no longer have a corresponding DB entry."""
    db = _get_db()
    try:
        from pathlib import Path
        from app.core.config import USER_DOCS_UPLOAD_DIR
        from app.modules.user_documents.models import UserDocument
        from app.modules.library.utils.storage_service import StorageService

        storage = StorageService(base_path=str(USER_DOCS_UPLOAD_DIR))
        upload_dir = Path(USER_DOCS_UPLOAD_DIR)

        if not upload_dir.exists():
            return {"cleaned": 0, "message": "Upload directory does not exist"}

        # Collect all known file URLs
        known_urls = set(
            row[0] for row in db.query(UserDocument.file_url).all() if row[0]
        )

        cleaned = 0
        for file_path in upload_dir.rglob("*"):
            if file_path.is_file():
                relative = str(file_path.relative_to(upload_dir))
                expected_url = f"/storage/{relative}"
                if expected_url not in known_urls:
                    try:
                        storage.delete_file(relative)
                        cleaned += 1
                    except Exception:
                        logger.warning("Failed to delete orphan file: %s", relative)

        logger.info("Cleanup: %d orphan files removed", cleaned)
        return {"cleaned": cleaned}
    except Exception as exc:
        logger.exception("Cleanup orphan files task failed")
    finally:
        db.close()


@celery_app.task(name="user_documents.tasks.retry_failed_extractions_cron", queue="cron")
def retry_failed_extractions_cron():
    """Cron task: retry failed extractions from the last 7 days."""
    db = _get_db()
    try:
        from app.modules.user_documents.services.user_document_extractor import UserDocumentExtractorService
        service = UserDocumentExtractorService(db=db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(service.retraiter_echecs(max_docs=50))
        logger.info("Retry failed extractions: %d retries", result.get("total_retries", 0))
        return result
    except Exception as exc:
        logger.exception("Retry failed extractions cron task failed")
    finally:
        db.close()


@celery_app.task(name="user_documents.tasks.notify_inactive_documents", queue="cron")
def notify_inactive_documents_task():
    """Notify users about documents unused for 90+ days."""
    db = _get_db()
    try:
        from sqlalchemy import and_
        from app.modules.user_documents.models import UserDocument

        threshold = datetime.now(timezone.utc) - timedelta(days=90)

        inactive_docs = (
            db.query(UserDocument)
            .filter(
                and_(
                    UserDocument.extraction_status == "success",
                    UserDocument.derniere_utilisation_at <= threshold,
                    UserDocument.nb_utilisations_rag > 0,
                )
            )
            .all()
        )

        notified_users = set()
        for doc in inactive_docs:
            if doc.user_id in notified_users:
                continue
            try:
                from app.modules.notifications.services.notification_service import NotificationService
                notif_svc = NotificationService(db=db)
                notif_svc.send_to_user(
                    user_id=doc.user_id,
                    title="Documents inactifs",
                    body=f"Vous avez des documents qui n'ont pas ete utilises depuis plus de 90 jours. Pensez a les revoir ou a les supprimer pour liberer de l'espace.",
                    type_notif="document_inactive",
                )
                notified_users.add(doc.user_id)
            except ImportError:
                logger.warning("NotificationService not available")
                break
            except Exception:
                logger.exception("Failed to notify user %s about inactive docs", doc.user_id)

        logger.info("Inactive doc notifications sent to %d users", len(notified_users))
        return {"notified_users": len(notified_users)}
    except Exception as exc:
        logger.exception("Notify inactive documents task failed")
    finally:
        db.close()
