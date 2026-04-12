from pydantic import BaseModel, Field
from typing import Optional


class FeedbackRequest(BaseModel):
    est_utile: bool
    langue: Optional[str] = Field(None, max_length=5)
    section_problematique: Optional[str] = Field(None, max_length=20)
    commentaire: Optional[str] = Field(None, max_length=500)
