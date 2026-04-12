import logging
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import USER_DOCS_UPLOAD_DIR
from app.modules.user_documents.schemas.requests import DocumentUpdateRequest
from app.modules.user_documents.schemas.responses import DocumentListResponse, DocumentDetailResponse
from app.modules.user_documents.routes.dependencies import (
    get_db,
    get_current_user,
    get_doc_service,
    get_extractor_service,
    get_rate_limiter_dependency,
    upload_rate_limiter,
)
from app.modules.user_documents.utils import FileValidator
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user-documents", tags=["User Documents"])


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    titre: str = Form(...),
    subject: str | None = Form(None),
    class_name: str | None = Form(None),
    language: str = Form("fr"),
    current_user: User = Depends(get_current_user),
    doc_service=Depends(get_doc_service),
    _rate_limit=Depends(get_rate_limiter_dependency(upload_rate_limiter)),
):
    """Upload a document. Validates file, checks quotas, saves and queues extraction."""
    validated = await FileValidator.validate_upload(file)

    try:
        result = await doc_service.valider_et_sauvegarder_upload(
            user_id=current_user.id,
            file_data=validated,
            titre=titre,
            subject=subject,
            class_name=class_name,
            language=language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return result


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    subject: str | None = Query(None),
    language: str | None = Query(None),
    extraction_status: str | None = Query(None),
    is_vectorized: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    doc_service=Depends(get_doc_service),
):
    """List user documents with filters."""
    result = await doc_service.lister_documents(
        user_id=current_user.id,
        subject=subject,
        language=language,
        extraction_status=extraction_status,
        is_vectorized=is_vectorized,
        page=page,
        limit=limit,
    )
    return {
        "total": result["total"],
        "espace_utilise_bytes": result["espace_utilise_bytes"],
        "espace_quota_bytes": result["espace_quota_bytes"],
        "documents": result["documents"],
    }


@router.get("/stats")
async def get_document_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get document statistics for the current user."""
    from sqlalchemy import func
    from app.modules.user_documents.models import UserDocument
    from app.modules.user_documents.utils import PLAN_QUOTAS

    nb_documents = (
        db.query(func.count(UserDocument.id))
        .filter(UserDocument.user_id == current_user.id)
        .scalar()
    )
    nb_vectorises = (
        db.query(func.count(UserDocument.id))
        .filter(UserDocument.user_id == current_user.id, UserDocument.is_vectorized == True)
        .scalar()
    )
    espace_utilise = (
        db.query(func.coalesce(func.sum(UserDocument.poids_octets), 0))
        .filter(UserDocument.user_id == current_user.id)
        .scalar()
    )

    plan = current_user.plan_effectif or "freemium"
    _, quota = PLAN_QUOTAS.get(plan, PLAN_QUOTAS["freemium"])
    taux = (espace_utilise / quota * 100) if quota > 0 else 0

    # Most used document
    plus_utilise = (
        db.query(UserDocument)
        .filter(UserDocument.user_id == current_user.id)
        .order_by(UserDocument.nb_utilisations_rag.desc())
        .first()
    )

    return {
        "nb_documents": nb_documents,
        "nb_vectorises": nb_vectorises,
        "espace_utilise": espace_utilise,
        "quota": quota,
        "taux_utilisation": round(taux, 2),
        "document_plus_utilise": plus_utilise.serialize_list_item() if plus_utilise else None,
    }


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: int,
    current_user: User = Depends(get_current_user),
    doc_service=Depends(get_doc_service),
):
    """Get detailed information about a document."""
    detail = await doc_service.obtenir_detail(document_id, current_user.id)
    text = detail.get("extracted_text", "") or ""
    return {
        "id": detail["id"],
        "titre": detail["titre"],
        "subject": detail.get("subject"),
        "class_name": detail.get("class_name"),
        "language": detail["language"],
        "nom_fichier_original": detail["nom_fichier_original"],
        "poids_octets": detail["poids_octets"],
        "nb_pages": detail.get("nb_pages"),
        "extraction_status": detail["extraction_status"],
        "is_vectorized": detail["is_vectorized"],
        "vectorization_status": detail.get("vectorization_status", "pending"),
        "nb_chunks": detail.get("nb_chunks"),
        "nb_utilisations_rag": detail.get("nb_utilisations_rag", 0),
        "derniere_utilisation_at": detail.get("derniere_utilisation_at"),
        "has_text": bool(text),
        "texte_preview": detail.get("extracted_text_preview"),
        "file_url": detail["file_url"],
        "mimetype": detail["mimetype"],
        "created_at": detail.get("created_at"),
    }


@router.patch("/{document_id}")
async def update_document(
    document_id: int,
    body: DocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update document metadata."""
    from app.modules.user_documents.models import UserDocument

    doc = (
        db.query(UserDocument)
        .filter(UserDocument.id == document_id, UserDocument.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc, field, value)

    db.commit()
    db.refresh(doc)
    return {"message": "Document mis a jour", "document": doc.serialize_list_item()}


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    doc_service=Depends(get_doc_service),
):
    """Delete a document and its associated files."""
    await doc_service.supprimer_document(document_id, current_user.id)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the original document file."""
    from app.modules.user_documents.models import UserDocument
    from app.modules.library.utils.storage_service import StorageService

    doc = (
        db.query(UserDocument)
        .filter(UserDocument.id == document_id, UserDocument.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")

    storage = StorageService(base_path=str(USER_DOCS_UPLOAD_DIR))
    relative_path = doc.file_url.replace("/storage/", "", 1) if doc.file_url else ""
    file_path = storage.base_path / relative_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="FILE_NOT_FOUND_ON_STORAGE")

    return FileResponse(
        path=str(file_path),
        media_type=doc.mimetype,
        filename=doc.nom_fichier_original,
    )


@router.post("/{document_id}/vectorize", status_code=202)
async def vectorize_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger vectorization for a document. Premium+ users only."""
    from app.modules.user_documents.models import UserDocument

    if current_user.plan_effectif in ("freemium", "access"):
        raise HTTPException(status_code=403, detail="PLAN_INSUFFISANT")

    doc = (
        db.query(UserDocument)
        .filter(UserDocument.id == document_id, UserDocument.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")

    if doc.extraction_status != "success":
        raise HTTPException(status_code=400, detail="EXTRACTION_NOT_COMPLETE")

    try:
        from app.modules.user_documents.jobs.tasks import vectorize_document_task
        doc.vectorization_status = "queued"
        db.commit()
        vectorize_document_task.delay(document_id=doc.id)
        return {"message": "Vectorisation lancee", "document_id": doc.id}
    except ImportError:
        raise HTTPException(status_code=501, detail="VECTORIZATION_UNAVAILABLE")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"VECTORIZE_ERROR: {str(exc)}")
