from pydantic import BaseModel, Field
from typing import Optional

class AnswerSubmitRequest(BaseModel):
    reponse: Optional[str] = Field(None, max_length=2000)
    qualite: Optional[int] = Field(None, ge=0, le=5)
    duree_secondes: Optional[int] = Field(None, ge=0)

class SectionCompleteRequest(BaseModel):
    pass
