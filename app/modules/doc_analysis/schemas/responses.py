from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class AnalysisResponse(BaseModel):
    document_id: int
    langue: str
    analysis_type: str
    key_points: List[str] = []
    concepts: List[str] = []
    tips: List[str] = []
    summary: Optional[str] = None
    methodologie: Optional[str] = None
    notions_prerequis: List[str] = []
    is_cached: bool
    analyzed_at: Optional[str] = None
    nb_acces: int = 0


class FeedbackResponse(BaseModel):
    message: str
    taux_utilite_actuel: Optional[float] = None
