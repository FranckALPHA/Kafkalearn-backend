from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class RegisterDeviceRequest(BaseModel):
    fcm_token: str = Field(..., min_length=10)
    platform: str = Field(..., pattern="^(android|ios|web)$")
    app_version: Optional[str] = Field(None, max_length=20)
    device_model: Optional[str] = Field(None, max_length=100)


class UpdatePreferencesRequest(BaseModel):
    quiz_dispo: Optional[bool] = None
    memory_review: Optional[bool] = None
    session_rappel: Optional[bool] = None
    streaks: Optional[bool] = None
    payment: Optional[bool] = None
    lacunes: Optional[bool] = None
    marketing: Optional[bool] = None
    heure_silencieuse_debut: Optional[str] = None
    heure_silencieuse_fin: Optional[str] = None
