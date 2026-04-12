from pydantic import BaseModel, Field, field_validator
from typing import Optional


class SessionCreateRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=100)
    titre: Optional[str] = Field(None, max_length=255)
    planned_start: str = Field(..., description="ISO datetime")
    planned_duration_minutes: int = Field(..., ge=5, le=480)
    ressource_principale_id: Optional[int] = None
    ressource_principale_type: Optional[str] = None
    is_ai_generated: bool = False
    humeur_debut: Optional[str] = None


class PingRequest(BaseModel):
    elapsed_client: Optional[int] = None


class MoodRequest(BaseModel):
    humeur_fin: Optional[str] = None
    note_session: Optional[str] = Field(None, max_length=2000)


class SessionStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=15)
    humeur_fin: Optional[str] = None
    note_session: Optional[str] = None


class TimetableEntryRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=100)
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
