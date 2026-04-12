from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class IngestReportResponse(BaseModel):
    job_id: str
    status: str
    nb_fichiers_total: int
    nb_traites: int
    nb_succes: int
    nb_echecs: int
    nb_doublons: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    erreurs_detail: List[dict] = []


class WorkerChunkResponse(BaseModel):
    documents: List[Dict[str, Any]]
