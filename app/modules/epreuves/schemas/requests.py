from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List


class DocumentFilterRequest(BaseModel):
    """Filtres pour la recherche de documents."""
    q: Optional[str] = Field(None, max_length=200, description="Recherche textuelle")
    matiere: Optional[str] = Field(None, max_length=100)
    niveau: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=20)
    annee: Optional[int] = Field(None, ge=1990, le=2030)
    region: Optional[str] = Field(None, max_length=100)
    type_doc: Optional[str] = Field(None, max_length=20)
    langue: Optional[str] = Field(None, max_length=5)
    difficulte_estimee: Optional[str] = Field(None, max_length=10)
    tri: str = Field("date_desc", description="date_desc|date_asc|vues_desc|nom_asc")

    @field_validator("q")
    @classmethod
    def q_not_empty(cls, v):
        if v and not v.strip():
            return None
        return v.strip() if v else v


class DocumentUploadRequest(BaseModel):
    """Metadata pour l'upload d'un document."""
    nom_affiche: Optional[str] = Field(None, max_length=255)
    matiere: Optional[str] = Field(None, max_length=100)
    niveau: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=20)
    annee: Optional[int] = Field(None, ge=1990, le=2030)
    type_doc: str = Field(..., max_length=20)
    sous_type: Optional[str] = Field(None, max_length=50)
    notion_principale: Optional[str] = Field(None, max_length=255)
    region: Optional[str] = Field(None, max_length=100)
    etablissement: Optional[str] = Field(None, max_length=255)
    duree: Optional[int] = Field(None, gt=0)
    coefficient: Optional[int] = Field(None, gt=0)
    total_points: Optional[int] = Field(None, gt=0)
    langue: str = Field("fr")
    difficulte_estimee: Optional[str] = Field(None, max_length=10)


class PlaylistCreateRequest(BaseModel):
    """Creation d'une playlist."""
    nom: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    objectif: Optional[str] = Field(None, max_length=100)
    matiere_cible: Optional[str] = Field(None, max_length=100)
    niveau_cible: Optional[str] = Field(None, max_length=50)


class PlaylistAddDocumentRequest(BaseModel):
    """Ajout d'un document a une playlist."""
    document_id: int = Field(..., gt=0)


class ViewLogRequest(BaseModel):
    """Log de consultation d'un document."""
    source: str = Field("view", description="view|download|recommendation|search")
    duree_consultation_sec: Optional[int] = Field(None, ge=0)
    a_scrolle: bool = False
