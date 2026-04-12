from pydantic import BaseModel, Field
from typing import List, Optional

class SubmitAnswerRequest(BaseModel):
    reponses: List[dict] = Field(..., description="List of {question_id, reponse}")
    duree_secondes: Optional[int] = Field(None, ge=0)
