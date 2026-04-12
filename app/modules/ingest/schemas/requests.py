from pydantic import BaseModel, Field
from typing import Optional


class FolderScanRequest(BaseModel):
    chemin_dossier: str = Field(..., min_length=1)


class WorkerResultRequest(BaseModel):
    worker_id: str
    succes: bool
    nb_chunks_embeds: int = 0
    erreur: Optional[str] = None
