from pydantic import BaseModel, Field
from typing import Optional

class DocumentUpdateRequest(BaseModel):
    titre: Optional[str] = Field(None, max_length=255)
    subject: Optional[str] = Field(None, max_length=100)
    class_name: Optional[str] = Field(None, max_length=50)
    language: Optional[str] = Field(None, pattern="^(fr|en)$")
