import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from app.modules.epreuves.schemas.requests import DocumentFilterRequest, DocumentUploadRequest, ViewLogRequest
from app.modules.epreuves.schemas.responses import (
    DocumentListResponse, DocumentDetailResponse, DocumentUploadResponse,
    TrendingResponse, RecommendationResponse, DocumentStatsResponse, FilterResponse,
)
from app.modules.epreuves.routes.dependencies import (
    get_db, get_current_user, get_optional_user, require_can_download,
    get_rate_limiter_dependency, epreuves_rate_limiter, download_rate_limiter,
    get_document_service, get_stats_service, get_filter_cache_service, get_recommendation_engine,
)
from app.modules.epreuves.routes.dependencies import get_document_service as get_doc_svc
from app.modules.epreuves.utils.file_validator import FileValidator
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/epreuves", tags=["Epreuves"])


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    q: Optional[str] = Query(None, max_length=200),
    matiere: Optional[str] = Query(None),
    niveau: Optional[str] = Query(None),
    serie: Optional[str] = Query(None),
    annee: Optional[int] = Query(None),
    region: Optional[str] = Query(None),
    type_doc: Optional[str] = Query(None),
    langue: Optional[str] = Query(None),
    difficulte_estimee: Optional[str] = Query(None),
    tri: str = Query("date_desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    doc_service=Depends(get_document_service),
):
    filters = {
        "q": q, "matiere": matiere, "niveau": niveau, "serie": serie,
        "annee": annee, "region": region, "type_doc": type_doc,
        "langue": langue, "difficulte_estimee": difficulte_estimee,
    }
    return await doc_service.liste_documents(filters=filters, sort=tri, page=page, limit=limit)


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    doc_id: int,
    current_user: User = Depends(get_optional_user),
    doc_service=Depends(get_document_service),
):
    doc = await doc_service.recuperer_par_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
    
    # Log view in background
    if current_user:
        try:
            from app.modules.epreuves.jobs.tasks import log_document_view_task
            log_document_view_task.delay(document_id=doc_id, user_id=str(current_user.id), source="direct")
        except Exception:
            pass
    else:
        try:
            from app.modules.epreuves.jobs.tasks import increment_document_stat_task
            increment_document_stat_task.delay(document_id=doc_id, stat_field="nb_vues")
        except Exception:
            pass
    
    return doc.serialize_detail()


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: int,
    current_user: User = Depends(require_can_download),
    doc_service=Depends(get_document_service),
):
    doc = await doc_service.recuperer_par_id(doc_id)
    if not doc or not doc.download_available:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
    
    from app.modules.epreuves.utils.storage import StorageService
    storage = StorageService()
    file_info = storage.stream_file(doc.chemin_final, filename=doc.nom_original)
    if not file_info:
        raise HTTPException(status_code=410, detail="FILE_MISSING")
    
    # Log download in background
    try:
        from app.modules.epreuves.jobs.tasks import log_download_task
        log_download_task.delay(document_id=doc_id, user_id=str(current_user.id))
    except Exception:
        pass
    
    return FileResponse(file_info["path"], filename=file_info["filename"], media_type=file_info["media_type"])


@router.get("/trending", response_model=TrendingResponse)
async def get_trending_documents(
    matiere: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=20),
    doc_service=Depends(get_document_service),
):
    results = await doc_service.obtenir_trending(periode_jours=7, matiere=matiere, limit=limit)
    return {"periode_jours": 7, "matiere": matiere, "documents": results}


@router.get("/recommandes", response_model=RecommendationResponse)
async def get_recommended_documents(
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=20),
    recommendation_engine=Depends(get_recommendation_engine),
):
    recs = recommendation_engine.recommander_mix(user_id=str(current_user.id), limit=limit)
    return {"recommandations": recs}


@router.get("/filtres", response_model=FilterResponse)
async def get_available_filters(
    filter_service=Depends(get_filter_cache_service),
):
    filters = filter_service.get_filters()
    return FilterResponse(**filters)


@router.get("/{doc_id}/stats", response_model=DocumentStatsResponse)
async def get_document_stats(
    doc_id: int,
    stats_service=Depends(get_stats_service),
):
    stats = stats_service.get_stats_document(doc_id)
    if not stats:
        raise HTTPException(status_code=404, detail="DOCUMENT_NOT_FOUND")
    return DocumentStatsResponse(**stats)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    nom_affiche: Optional[str] = Query(None),
    matiere: Optional[str] = Query(None),
    niveau: Optional[str] = Query(None),
    annee: Optional[int] = Query(None),
    type_doc: str = Query("epreuve"),
    current_user: User = Depends(get_current_user),
    doc_service=Depends(get_document_service),
):
    # Validate file
    file_data = await FileValidator.validate_upload(file)
    
    metadata = {
        "nom_original": file.filename,
        "nom_affiche": nom_affiche,
        "matiere": matiere,
        "niveau": niveau,
        "annee": annee,
        "type_doc": type_doc,
    }
    
    result = await doc_service.ajouter_document(
        file_data=file_data,
        metadata=metadata,
        uploaded_by=str(current_user.id),
    )
    
    return DocumentUploadResponse(**result)
