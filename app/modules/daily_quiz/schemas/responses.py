from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class QuizResponse(BaseModel):
    quiz: dict
    deja_tente: bool
    ma_tentative: Optional[dict] = None
    temps_restant_secondes: int

class SubmitResultResponse(BaseModel):
    score: int
    score_pourcentage: float
    correction: List[dict]
    streak: int
    message_coaching: str

class LeaderboardResponse(BaseModel):
    month_year: str
    top_entries: List[dict]
    mon_rang: Optional[dict] = None
    total_participants: int
