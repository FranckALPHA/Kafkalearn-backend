from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChunkResponse(BaseModel):
    """Un chunk de document retourné."""
    chunk_id: int
    document_id: int
    document_nom: str
    texte_chunk: str
    matiere: Optional[str]
    niveau: Optional[str]
    score_rrf: Optional[float]
    rang: int
    est_cite: bool = False


class IAReponse(BaseModel):
    """Réponse générée par l'IA."""
    texte: str
    sources_citees: Optional[List[int]] = Field(None, description="Liste des chunk_id cités")
    mode: str
    confiance: Optional[float] = None


class QuotaRestant(BaseModel):
    daily: int
    monthly: int
    daily_used: int
    monthly_used: int


class SearchResponse(BaseModel):
    """Réponse complète de la recherche."""
    requete: str
    requete_normalisee: str
    intention_detectee: Optional[str]
    matiere_detectee: Optional[str]
    nb_resultats: int
    chunks: List[ChunkResponse]
    sources: List[Dict[str, Any]]
    reponse_ia: Optional[IAReponse] = None
    erreur_ia: Optional[str] = None
    quota_restant: Optional[QuotaRestant] = None
    latence_ms: int
    search_log_id: Optional[int] = None


class FeedbackResponse(BaseModel):
    message: str
    search_log_id: int
    rating: int


class SearchLogMinimal(BaseModel):
    """Pour l'historique utilisateur."""
    id: int
    texte_requete: str
    intention_detectee: Optional[str]
    matiere_detectee: Optional[str]
    nb_resultats: int
    reponse_ia_generee: bool
    feedback_rating: Optional[int]
    created_at: Optional[datetime]


class SearchAnalyticsResponse(BaseModel):
    """Pour les analytics SuperAdmin."""
    total_searches: int
    searches_with_ia: int
    avg_latency_ms: float
    avg_chunks_returned: float
    top_matieres: List[Dict[str, Any]]
    top_intentions: List[Dict[str, Any]]
    feedback_distribution: Dict[str, int]
    period: str


class SuggestionResponse(BaseModel):
    """Suggestions personnalisées."""
    suggestions: List[str]
    generated_at: Optional[datetime]
    expires_at: Optional[datetime]
