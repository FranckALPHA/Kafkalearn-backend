from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class DocumentListResponse(BaseModel):
    total: int
    espace_utilise_bytes: int
    espace_quota_bytes: int
    documents: List[Dict[str, Any]]

class DocumentDetailResponse(BaseModel):
    id: int
    titre: str
    subject: Optional[str] = None
    class_name: Optional[str] = None
    language: str
    nom_fichier_original: str
    poids_octets: int
    nb_pages: Optional[int] = None
    extraction_status: str
    is_vectorized: bool
    vectorization_status: str
    nb_chunks: Optional[int] = None
    nb_utilisations_rag: int
    derniere_utilisation_at: Optional[str] = None
    has_text: bool
    texte_preview: Optional[str] = None
    file_url: str
    mimetype: str
    created_at: Optional[str] = None
