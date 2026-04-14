from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class SessionResponse(BaseModel):
    id: int
    subject: str
    titre: Optional[str] = None
    planned_start: Optional[str] = None
    planned_end: Optional[str] = None
    status: str
    accumulated_seconds: int
    concentration_ratio: Optional[float] = None
    is_ai_generated: bool
    ressource_principale_id: Optional[int] = None
    ressource_principale_type: Optional[str] = None
    humeur_debut: Optional[str] = None
    note_session: Optional[str] = None


class SessionListResponse(BaseModel):
    total: int
    page: int
    limit: int
    sessions: List[Dict[str, Any]]


class SuggestionsResponse(BaseModel):
    date: str
    matieres_du_jour: List[str]
    suggestions: List[Dict[str, Any]]
    cached: bool
    generated_at: Optional[str] = None


class HeatmapResponse(BaseModel):
    data: List[Dict[str, Any]]
    total: int
    max_count: int


class CoachInsightsResponse(BaseModel):
    insights: List[Dict[str, Any]]
    generated_at: Optional[str] = None


class PerformanceReportResponse(BaseModel):
    periode_jours: int
    total_sessions: int
    total_heures_etude: float
    avg_concentration: float
    subjects_breakdown: Dict[str, Any]
    streak: int
