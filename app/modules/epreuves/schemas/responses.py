from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class DocumentListResponse(BaseModel):
    """Reponse de liste de documents."""
    total: int
    page: int
    limit: int
    moteur: str = "sql"
    documents: List[Dict[str, Any]]


class DocumentDetailResponse(BaseModel):
    """Reponse detail d'un document."""
    id: int
    nom_original: str
    nom_affiche: Optional[str]
    matiere: Optional[str]
    niveau: Optional[str]
    serie: Optional[str]
    annee: Optional[int]
    region: Optional[str]
    type_doc: str
    sous_type: Optional[str]
    notion_principale: Optional[str]
    difficulte_estimee: Optional[str]
    duree: Optional[int]
    coefficient: Optional[int]
    total_points: Optional[int]
    langue: str
    nb_vues: int
    nb_telechargements: int
    nb_favoris: int
    is_validated: bool
    score_moyen_utilisateurs: Optional[float]
    etablissement: Optional[str]
    mots_cles: Optional[List[str]]
    created_at: Optional[str]


class DocumentUploadResponse(BaseModel):
    """Reponse apres upload de document."""
    document_id: int
    is_duplicate: bool
    ingest_status: str
    message: Optional[str] = None


class PlaylistResponse(BaseModel):
    """Reponse detail playlist."""
    id: int
    nom: str
    description: Optional[str]
    objectif: Optional[str]
    nb_documents: int
    is_public: bool
    lien_partage: Optional[str]
    matiere_cible: Optional[str]
    niveau_cible: Optional[str]
    documents: List[Dict[str, Any]] = []
    created_at: Optional[str]
    updated_at: Optional[str]


class PlaylistListResponse(BaseModel):
    """Reponse liste de playlists."""
    playlists: List[Dict[str, Any]]
    total: int


class TrendingResponse(BaseModel):
    """Reponse documents trending."""
    periode_jours: int
    matiere: Optional[str]
    documents: List[Dict[str, Any]]


class RecommendationResponse(BaseModel):
    """Reponse recommandations."""
    recommandations: List[Dict[str, Any]]


class DocumentStatsResponse(BaseModel):
    """Statistiques d'un document."""
    document_id: int
    nb_vues: int
    nb_telechargements: int
    nb_favoris: int
    nb_tentatives_ia: int
    score_moyen: Optional[float]
    vues_recentes_7j: int = 0


class FilterResponse(BaseModel):
    """Reponse filtres disponibles."""
    matieres: List[str]
    niveaux: List[str]
    series: List[str]
    annees: List[int]
    regions: List[str]
    types: List[str]
    langues: List[str]
