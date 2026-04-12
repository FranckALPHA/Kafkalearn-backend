import hashlib
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from redis import Redis
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import USER_DOCS_UPLOAD_DIR
from app.modules.user_documents.models import UserDocument, UserDocumentChunk
from app.modules.user_documents.services.base import UserDocumentsBaseService
from app.modules.user_documents.utils import FileValidator, PLAN_QUOTAS
from app.modules.library.utils.storage_service import StorageService
from app.modules.users.models.user import User

logger = logging.getLogger(__name__)

# Try to import Celery tasks; fall back gracefully
try:
    from app.modules.user_documents.jobs.tasks import extract_document_text_task
    CELERY_EXTRACT_AVAILABLE = True
except ImportError:
    extract_document_text_task = None  # type: ignore
    CELERY_EXTRACT_AVAILABLE = False


class UserDocumentService(UserDocumentsBaseService):
    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    # ------------------------------------------------------------------
    # Upload & save
    # ------------------------------------------------------------------
    async def valider_et_sauvegarder_upload(
        self,
        user_id,
        file_data,
        titre: str,
        subject: str = None,
        class_name: str = None,
        language: str = "fr",
    ) -> dict:
        """Validate quotas, check dedup, save file, create DB record, queue extraction."""
        # 1. Verify quotas
        file_bytes = file_data.get("file_bytes")
        await self._verifier_quotas(user_id, len(file_bytes))

        # 2. Compute hash for dedup
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        # 3. Check dedup
        existing = (
            self.db.query(UserDocument)
            .filter(
                UserDocument.user_id == user_id,
                UserDocument.hash_contenu == sha256_hash,
            )
            .first()
        )
        if existing:
            return {
                "document_id": existing.id,
                "message": "Document duplique deja existant",
                "is_duplicate": True,
                "extraction_status": existing.extraction_status,
            }

        # 4. Save file via StorageService
        storage = StorageService(base_path=str(USER_DOCS_UPLOAD_DIR))
        safe_filename = file_data.get("safe_filename", f"{sha256_hash[:16]}.pdf")
        file_url = storage.save_file(
            file_content=file_bytes,
            filename=safe_filename,
            content_type=file_data.get("mimetype", "application/pdf"),
            folder=str(user_id),
        )

        # 5. Create UserDocument record
        doc = UserDocument(
            user_id=user_id,
            titre=titre,
            subject=subject,
            class_name=class_name,
            language=language,
            nom_fichier_original=file_data.get("original_filename", "document"),
            nom_fichier_stocke=safe_filename,
            file_url=file_url,
            mimetype=file_data.get("mimetype", "application/pdf"),
            poids_octets=len(file_bytes),
            hash_contenu=sha256_hash,
            extraction_status="pending",
            vectorization_status="pending",
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        # 6. Queue extraction task
        if CELERY_EXTRACT_AVAILABLE and extract_document_text_task is not None:
            try:
                extract_document_text_task.delay(document_id=doc.id)
            except Exception:
                logger.exception("Failed to enqueue extraction task for doc %s", doc.id)

        return {
            "document_id": doc.id,
            "message": "Document upload avec succes",
            "is_duplicate": False,
            "extraction_status": doc.extraction_status,
        }

    # ------------------------------------------------------------------
    # Quota verification
    # ------------------------------------------------------------------
    async def _verifier_quotas(self, user_id, new_file_bytes: int):
        """Check user plan quotas and raise ValueError if exceeded."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        plan = user.plan_effectif
        if plan not in PLAN_QUOTAS:
            plan = "freemium"

        max_docs, max_bytes = PLAN_QUOTAS[plan]

        # Count existing documents
        doc_count = (
            self.db.query(func.count(UserDocument.id))
            .filter(UserDocument.user_id == user_id)
            .scalar()
        )
        if doc_count >= max_docs:
            raise ValueError(
                f"QUOTA_DEPASSE: nombre max de documents ({max_docs}) atteint pour le plan {plan}"
            )

        # Sum existing file sizes
        total_bytes = (
            self.db.query(func.coalesce(func.sum(UserDocument.poids_octets), 0))
            .filter(UserDocument.user_id == user_id)
            .scalar()
        )
        if total_bytes + new_file_bytes > max_bytes:
            max_mb = max_bytes / (1024 * 1024)
            used_mb = total_bytes / (1024 * 1024)
            new_mb = new_file_bytes / (1024 * 1024)
            raise ValueError(
                f"QUOTA_DEPASSE: espace max ({max_mb:.0f}MB) depasse. "
                f"Utilise: {used_mb:.1f}MB, nouveau: {new_mb:.1f}MB"
            )

    # ------------------------------------------------------------------
    # List documents
    # ------------------------------------------------------------------
    async def lister_documents(
        self,
        user_id,
        subject: str = None,
        language: str = None,
        extraction_status: str = None,
        is_vectorized: bool = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """List documents with filters, return paginated results with quota info."""
        query = self.db.query(UserDocument).filter(UserDocument.user_id == user_id)

        if subject:
            query = query.filter(UserDocument.subject == subject)
        if language:
            query = query.filter(UserDocument.language == language)
        if extraction_status:
            query = query.filter(UserDocument.extraction_status == extraction_status)
        if is_vectorized is not None:
            query = query.filter(UserDocument.is_vectorized == is_vectorized)

        total = query.count()

        espace_utilise = (
            self.db.query(func.coalesce(func.sum(UserDocument.poids_octets), 0))
            .filter(UserDocument.user_id == user_id)
            .scalar()
        )

        user = self.db.query(User).filter(User.id == user_id).first()
        plan = user.plan_effectif if user else "freemium"
        _, espace_quota = PLAN_QUOTAS.get(plan, PLAN_QUOTAS["freemium"])

        offset = (page - 1) * limit
        docs = query.order_by(UserDocument.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total": total,
            "espace_utilise_bytes": espace_utilise,
            "espace_quota_bytes": espace_quota,
            "documents": [d.serialize_list_item() for d in docs],
            "page": page,
            "limit": limit,
        }

    # ------------------------------------------------------------------
    # Delete document
    # ------------------------------------------------------------------
    async def supprimer_document(self, document_id: int, user_id) -> dict:
        """Verify ownership, delete chunks, delete physical file, soft-delete document."""
        doc = self._verify_ownership(document_id, user_id)

        # Delete associated chunks
        self.db.query(UserDocumentChunk).filter(
            UserDocumentChunk.document_id == document_id
        ).delete(synchronize_session="fetch")

        # Delete physical file
        storage = StorageService(base_path=str(USER_DOCS_UPLOAD_DIR))
        # Extract relative path from file_url (strip /storage/ prefix)
        relative_path = doc.file_url.replace("/storage/", "", 1) if doc.file_url else ""
        if relative_path:
            storage.delete_file(relative_path)

        # Soft-delete: mark extraction_status and clean up
        doc.extraction_status = "failed"
        doc.vectorization_status = "failed"
        self.db.delete(doc)
        self.db.commit()

        return {"message": "Document supprime avec succes", "document_id": document_id}

    # ------------------------------------------------------------------
    # Get document detail
    # ------------------------------------------------------------------
    async def obtenir_detail(self, document_id: int, user_id) -> dict:
        """Verify ownership and return serialized detail."""
        doc = self._verify_ownership(document_id, user_id)
        return doc.serialize_detail()

    # ------------------------------------------------------------------
    # Ownership verification
    # ------------------------------------------------------------------
    def _verify_ownership(self, document_id: int, user_id) -> UserDocument:
        """Verify document exists and belongs to user. Raises HTTPException on failure."""
        doc = (
            self.db.query(UserDocument)
            .filter(UserDocument.id == document_id)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
        if doc.user_id != user_id:
            raise HTTPException(status_code=403, detail="NOT_OWNER")
        return doc

    # ------------------------------------------------------------------
    # Increment usage counter
    # ------------------------------------------------------------------
    async def incrementer_utilisation(self, document_id: int):
        """Increment nb_utilisations_rag and update derniere_utilisation_at."""
        self.db.query(UserDocument).filter(
            UserDocument.id == document_id
        ).update(
            {
                UserDocument.nb_utilisations_rag: UserDocument.nb_utilisations_rag + 1,
                UserDocument.derniere_utilisation_at: datetime.now(timezone.utc),
            },
            synchronize_session="fetch",
        )
        self.db.commit()
