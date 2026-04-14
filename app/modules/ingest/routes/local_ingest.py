"""
routes/local_ingest.py
======================
Ingestion locale de dossiers de documents PDF.

Permet d'uploader un dossier entier de PDFs. Le système :
1. Supprime automatiquement les fichiers non-PDF du dossier
2. Extrait le texte de chaque PDF (natif ou OCR pour les scannés)
3. Détecte les métadonnées (matière, niveau, notion)
4. Crée les documents en base de données
5. Génère automatiquement des flashcards/QCM pour les leçons
6. Renomme les PDFs traités et les archive
7. Vide et supprime le dossier source

Usage :
    POST /api/v1/ingest/local-folder
    {
        "folder_path": "/home/user/documents/epreuves",
        "force": false
    }
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.users.routes.dependencies import (
    get_current_user,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingest - Local Folder"])


class LocalFolderIngestRequest(BaseModel):
    folder_path: str = Field(..., description="Chemin absolu du dossier contenant les PDFs")
    force: bool = Field(False, description="Forcer la reingestion des doublons")


@router.post(
    "/local-folder",
    summary="Ingérer un dossier de PDFs",
    description="""
**Scanne un dossier local et ingère tous les PDFs dans la plateforme.**

**Ce qui se passe automatiquement :**
1. Supprime les fichiers non-PDF du dossier source
2. Extrait le texte de chaque PDF (natif ou OCR pour les scannés)
3. Détecte les métadonnées (matière, niveau, notion) via le nom du fichier ou LLM
4. Crée les documents en base de données
5. Génère automatiquement des flashcards/QCM pour les leçons/cours
6. Renomme les PDFs traités (`{matiere}_{niveau}_{notion}_{hash}.pdf`) et les archive
7. Vide et supprime le dossier source

**Traitement asynchrone** via Celery — retourne immédiatement un `task_id`.
Utilisez `GET /ingest/local-folder/status/{task_id}` pour suivre la progression.

**Exemple de réponse :**
```json
{
  "task_id": "abc-123",
  "status": "queued",
  "pdf_count": 44,
  "message": "Ingestion queued for 44 PDFs."
}
```
    """,
)
async def ingest_local_folder(
    payload: LocalFolderIngestRequest,
    current_user: User = Depends(get_current_user),
):
    """Ingest local folder with PDFs → async Celery task."""
    import os
    from pathlib import Path

    folder = Path(payload.folder_path)
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Folder not found: {payload.folder_path}")
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {payload.folder_path}")

    # Vérifier qu'il y a des PDFs
    pdf_count = len(list(folder.glob("*.pdf")))
    if pdf_count == 0:
        raise HTTPException(status_code=404, detail="No PDF files found in folder")

    # Queue Celery task
    try:
        from app.modules.ingest.jobs.ingest_folder_tasks import ingest_folder_task
        result = ingest_folder_task.delay(
            folder_path=str(folder.resolve()),
            uploaded_by=str(current_user.id),
            force=payload.force,
        )
        return {
            "task_id": result.id,
            "status": "queued",
            "folder": str(folder.resolve()),
            "pdf_count": pdf_count,
            "message": f"Ingestion queued for {pdf_count} PDFs. Check status via task_id.",
        }
    except Exception as e:
        logger.error(f"Failed to queue ingest task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue ingest task: {str(e)}")


@router.get(
    "/local-folder/status/{task_id}",
    summary="Statut d'une tâche d'ingestion",
    description="""
**Vérifie le statut d'une tâche d'ingestion de PDFs.**

Utilisez le `task_id` retourné par `POST /ingest/local-folder` pour suivre la progression.

**Réponses possibles :**
- `PENDING` : La tâche est en file d'attente
- `STARTED` : La tâche est en cours d'exécution
- `completed` : La tâche est terminée — le champ `result` contient les détails
- `failed` : La tâche a échoué — le champ `error` contient le message d'erreur

**Exemple de résultat complété :**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "result": {
    "ingested": 40,
    "skipped": 3,
    "errors": 1,
    "memory_queued": 12,
    "archive_path": "/path/to/archive/20260414_120000"
  }
}
```
    """,
)
async def get_ingest_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Check status of an ingest task by task_id."""
    try:
        from celery.result import AsyncResult
        from app.modules.ingest.jobs.ingest_folder_tasks import ingest_folder_task

        result = AsyncResult(task_id, app=ingest_folder_task.app)

        if result.ready():
            return {
                "task_id": task_id,
                "status": "completed",
                "result": result.get(),
            }
        elif result.failed():
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(result.result),
            }
        else:
            return {
                "task_id": task_id,
                "status": result.status,  # PENDING, STARTED, RETRY
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check status: {str(e)}")
