from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.modules.doc_analysis.schemas.requests import FeedbackRequest
from app.modules.doc_analysis.schemas.responses import AnalysisResponse, FeedbackResponse
from app.modules.doc_analysis.routes.dependencies import (
    get_db,
    get_current_user,
    get_analysis_service,
    get_feedback_service,
    analyze_rate_limiter,
    feedback_rate_limiter,
    get_rate_limiter_dependency,
)
from app.modules.doc_analysis.models import DocumentAnalysis
from app.modules.users.models import User

PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited", "school"]

router = APIRouter(prefix="/documents", tags=["Document Analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    dependencies=[Depends(get_rate_limiter_dependency(analyze_rate_limiter))],
)
async def analyze_document(
    document_id: int,
    langue: str = "fr",
    current_user: User = Depends(get_current_user),
    analysis_service=Depends(get_analysis_service),
):
    """Analyze a document: returns cached analysis or generates a new one."""
    try:
        result = await analysis_service.analyser_ou_retourner_cache(
            document_id=document_id,
            langue=langue,
            user_plan=getattr(current_user, "plan_effectif", "freemium"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ANALYSIS_FAILED: {exc}")

    return AnalysisResponse(
        document_id=result["document_id"],
        langue=result["langue"],
        analysis_type=result["analysis_type"],
        key_points=result.get("key_points", []),
        concepts=result.get("concepts", []),
        tips=result.get("tips", []),
        summary=result.get("summary"),
        methodologie=result.get("methodologie"),
        notions_prerequis=result.get("notions_prerequis", []),
        is_cached=result.get("is_cached", False),
        analyzed_at=result.get("analyzed_at"),
        nb_acces=result.get("nb_acces", 0),
    )


@router.get("/analyze/{document_id}", response_model=AnalysisResponse)
async def get_cached_analysis(
    document_id: int,
    langue: str = "fr",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get cached analysis only. Returns 404 if not exists."""
    analysis = (
        db.query(DocumentAnalysis)
        .filter(
            DocumentAnalysis.document_id == document_id,
            DocumentAnalysis.langue == langue,
        )
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="ANALYSIS_NOT_FOUND")

    return AnalysisResponse(
        document_id=analysis.document_id,
        langue=analysis.langue,
        analysis_type=analysis.analysis_type,
        key_points=analysis.key_points or [],
        concepts=analysis.concepts or [],
        tips=analysis.tips or [],
        summary=analysis.summary,
        methodologie=analysis.methodologie,
        notions_prerequis=analysis.notions_prerequis or [],
        is_cached=True,
        analyzed_at=analysis.analyzed_at.isoformat() if analysis.analyzed_at else None,
        nb_acces=analysis.nb_acces,
    )


@router.post("/analyze/{document_id}/refresh", response_model=AnalysisResponse)
async def refresh_analysis(
    document_id: int,
    langue: str = "fr",
    current_user: User = Depends(get_current_user),
    analysis_service=Depends(get_analysis_service),
):
    """Force regeneration of analysis (tous plans, 1/24h rate limit)."""
    try:
        result = await analysis_service.forcer_regeneration(
            document_id=document_id,
            langue=langue,
            user_id=str(current_user.id),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"REFRESH_FAILED: {exc}")

    return AnalysisResponse(
        document_id=result["document_id"],
        langue=result["langue"],
        analysis_type=result["analysis_type"],
        key_points=result.get("key_points", []),
        concepts=result.get("concepts", []),
        tips=result.get("tips", []),
        summary=result.get("summary"),
        methodologie=result.get("methodologie"),
        notions_prerequis=result.get("notions_prerequis", []),
        is_cached=False,
        analyzed_at=result.get("analyzed_at"),
        nb_acces=result.get("nb_acces", 0),
    )


@router.post(
    "/analyze/{document_id}/feedback",
    response_model=FeedbackResponse,
    dependencies=[Depends(get_rate_limiter_dependency(feedback_rate_limiter))],
)
async def submit_feedback(
    document_id: int,
    feedback: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    feedback_service=Depends(get_feedback_service),
    db: Session = Depends(get_db),
):
    """Submit feedback on a document analysis."""
    analysis = (
        db.query(DocumentAnalysis)
        .filter(
            DocumentAnalysis.document_id == document_id,
            DocumentAnalysis.langue == (feedback.langue or "fr"),
        )
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="ANALYSIS_NOT_FOUND")

    try:
        result = await feedback_service.enregistrer_feedback(
            analysis_id=analysis.id,
            user_id=str(current_user.id),
            est_utile=feedback.est_utile,
            section_problematique=feedback.section_problematique,
            commentaire=feedback.commentaire,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return FeedbackResponse(
        message="FEEDBACK_RECORDED",
        taux_utilite_actuel=result.get("taux_utilite"),
    )
