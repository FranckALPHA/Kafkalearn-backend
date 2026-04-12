from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class NotificationHistoryResponse(BaseModel):
    total: int
    nb_non_lues: int
    notifications: List[Dict[str, Any]]


class PreferencesResponse(BaseModel):
    quiz_dispo: bool = True
    memory_review: bool = True
    session_rappel: bool = True
    streaks: bool = True
    payment: bool = True
    lacunes: bool = True
    marketing: bool = False
    heure_silencieuse_debut: Optional[str] = None
    heure_silencieuse_fin: Optional[str] = None
