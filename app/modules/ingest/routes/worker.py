"""
routes/worker.py
================
Worker endpoints for the ingest module.
"""
import logging

from fastapi import APIRouter, Depends, Header

from app.modules.ingest.schemas.requests import WorkerResultRequest
from app.modules.ingest.schemas.responses import WorkerChunkResponse
from app.modules.ingest.routes.dependencies import (
    get_worker_coordinator,
    verify_worker_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest/worker", tags=["Ingest - Worker"])


@router.get("/not-embedded", response_model=WorkerChunkResponse)
async def get_not_embedded_documents(
    limit: int = 10,
    x_worker_token: str = Header(None),
    worker_coordinator=Depends(get_worker_coordinator),
    _token_valid=Depends(verify_worker_token),
):
    """Return list of documents pending embedding, protected by worker_token header."""
    documents = worker_coordinator.lister_documents_a_embedder(limit=limit)
    return WorkerChunkResponse(documents=documents)


@router.post("/save-results/{doc_id}")
async def save_worker_results(
    doc_id: int,
    request: WorkerResultRequest,
    x_worker_token: str = Header(None),
    worker_coordinator=Depends(get_worker_coordinator),
    _token_valid=Depends(verify_worker_token),
):
    """Save worker results, protected by worker_token header."""
    worker_coordinator.sauvegarder_resultats_worker(
        doc_id=doc_id,
        worker_id=request.worker_id,
        succes=request.succes,
        nb_chunks=request.nb_chunks_embeds,
        erreur=request.erreur,
    )
    return {"message": "Worker results saved", "doc_id": doc_id}
