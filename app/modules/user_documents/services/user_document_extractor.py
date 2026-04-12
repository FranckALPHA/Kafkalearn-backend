import logging
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import USER_DOCS_UPLOAD_DIR
from app.modules.user_documents.models import UserDocument
from app.modules.user_documents.services.base import UserDocumentsBaseService
from app.modules.user_documents.utils import TextCleaner
from app.modules.library.utils.storage_service import StorageService
from app.modules.users.models.user import User

logger = logging.getLogger(__name__)

# Try to import Celery tasks; fall back gracefully
try:
    from app.modules.user_documents.jobs.tasks import vectorize_document_task
    CELERY_VECTORIZE_AVAILABLE = True
except ImportError:
    vectorize_document_task = None  # type: ignore
    CELERY_VECTORIZE_AVAILABLE = False

# Try to import NotificationService
try:
    from app.modules.notifications.services.notification_service import NotificationService
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NotificationService = None  # type: ignore
    NOTIFICATION_AVAILABLE = False


class UserDocumentExtractorService(UserDocumentsBaseService):
    def extraire(self, document_id: int) -> dict:
        """Extract text from a document.

        Steps:
        1. Get UserDocument
        2. Set status=processing
        3. Read file from storage
        4. Extract text (PDF via pdfplumber, else fallback)
        5. Clean text via TextCleaner
        6. Update document with extracted_text, nb_pages, extraction_status
        7. If success and plan allows vectorization, queue vectorize task
        """
        doc = (
            self.db.query(UserDocument)
            .filter(UserDocument.id == document_id)
            .first()
        )
        if not doc:
            return {"status": "error", "message": "DOCUMENT_NOT_FOUND"}

        # Mark as processing
        doc.extraction_status = "processing"
        doc.extraction_error = None
        self.db.commit()

        extracted_text = None
        nb_pages = None

        try:
            # Read file from storage
            storage = StorageService(base_path=str(USER_DOCS_UPLOAD_DIR))
            relative_path = doc.file_url.replace("/storage/", "", 1) if doc.file_url else ""

            if not relative_path or not storage.file_exists(relative_path):
                raise FileNotFoundError(f"File not found: {relative_path}")

            file_handle = storage.get_file(relative_path)
            if file_handle is None:
                raise FileNotFoundError(f"Cannot read file: {relative_path}")

            file_bytes = file_handle.read()
            file_handle.close()

            # Extract text based on mime type
            if doc.mimetype == "application/pdf":
                extracted_text, nb_pages = self._extract_pdf(file_bytes)
            else:
                # Fallback for doc/docx - simple approach
                extracted_text = f"[Texte brut - {doc.mimetype}] {doc.nom_fichier_original}"
                nb_pages = 1

            # Clean text
            if extracted_text:
                extracted_text = TextCleaner.clean(extracted_text)

            if extracted_text:
                doc.extracted_text = extracted_text
                doc.nb_pages = nb_pages or 0
                doc.extraction_status = "success"
                doc.extraction_error = None
                self.db.commit()

                logger.info(
                    "Extraction succeeded for doc %s: %d chars, %d pages",
                    document_id,
                    len(extracted_text),
                    doc.nb_pages,
                )

                # Notify user
                self._notifier_extraction_succes(doc.user_id, doc.titre)

                # Queue vectorization if plan allows
                self._queue_vectorization_if_allowed(doc)
            else:
                doc.extraction_status = "failed"
                doc.extraction_error = "Aucun texte extrait du document"
                self.db.commit()

        except Exception as exc:
            logger.exception("Extraction failed for doc %s", document_id)
            doc.extraction_status = "failed"
            doc.extraction_error = str(exc)[:500]
            self.db.commit()

        return {
            "status": doc.extraction_status,
            "document_id": document_id,
            "nb_pages": doc.nb_pages,
            "error": doc.extraction_error,
        }

    # ------------------------------------------------------------------
    # Retry failed extractions
    # ------------------------------------------------------------------
    async def retraiter_echecs(self, max_docs: int = 50) -> dict:
        """Retry failed extractions from the last 7 days."""
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

        failed_docs = (
            self.db.query(UserDocument)
            .filter(
                and_(
                    UserDocument.extraction_status == "failed",
                    UserDocument.updated_at >= seven_days_ago,
                )
            )
            .limit(max_docs)
            .all()
        )

        results = []
        for doc in failed_docs:
            try:
                result = self.extraire(doc.id)
                results.append({"document_id": doc.id, "status": result["status"]})
            except Exception as exc:
                logger.exception("Retry failed for doc %s", doc.id)
                results.append({"document_id": doc.id, "status": "error", "error": str(exc)})

        return {
            "total_retries": len(failed_docs),
            "results": results,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _extract_pdf(self, file_bytes: bytes):
        """Extract text from PDF using pdfplumber. Returns (text, nb_pages)."""
        try:
            import io
            import pdfplumber

            pdf_file = io.BytesIO(file_bytes)
            all_text = []
            page_count = 0

            with pdfplumber.open(pdf_file) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text.append(text)

            return "\n\n".join(all_text), page_count
        except ImportError:
            logger.warning("pdfplumber not installed, falling back to raw decode")
            return file_bytes.decode("utf-8", errors="ignore"), 1
        except Exception:
            logger.exception("pdfplumber extraction failed")
            return None, None

    def _queue_vectorization_if_allowed(self, doc: UserDocument):
        """Queue vectorization task if user plan supports it."""
        user = self.db.query(User).filter(User.id == doc.user_id).first()
        if not user:
            return

        # Freemium users do not get vectorization
        if user.plan_effectif == "freemium":
            logger.info("Skipping vectorization for freemium user %s", doc.user_id)
            return

        if CELERY_VECTORIZE_AVAILABLE and vectorize_document_task is not None:
            try:
                doc.vectorization_status = "queued"
                self.db.commit()
                vectorize_document_task.delay(document_id=doc.id)
                logger.info("Queued vectorization for doc %s", doc.id)
            except Exception:
                logger.exception("Failed to enqueue vectorization for doc %s", doc.id)
                doc.vectorization_status = "pending"
                self.db.commit()
        else:
            logger.warning("Celery vectorize task not available")

    async def _notifier_extraction_succes(self, user_id, titre: str):
        """Notify user of successful extraction (best-effort)."""
        if not NOTIFICATION_AVAILABLE or NotificationService is None:
            return
        try:
            notif_svc = NotificationService(db=self.db, redis=self.redis)
            notif_svc.send_to_user(
                user_id=user_id,
                title="Extraction terminee",
                body=f"Votre document '{titre}' a ete traite avec succes.",
                type_notif="document_ready",
            )
        except Exception:
            logger.exception("Failed to send extraction success notification")
