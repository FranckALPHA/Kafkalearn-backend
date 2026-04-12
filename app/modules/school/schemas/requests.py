from pydantic import BaseModel, Field
from typing import Optional


class SchoolCreateRequest(BaseModel):
    nom: str = Field(..., min_length=2, max_length=255)
    ville: str = Field(..., min_length=1, max_length=100)
    pays: str = Field("CM", max_length=5)
    region: Optional[str] = Field(None, max_length=100)
    nb_sieges: int = Field(..., ge=10)
    description: Optional[str] = Field(None, max_length=1000)


class SchoolJoinRequest(BaseModel):
    code: str = Field(..., min_length=7, max_length=7)


class CSVImportRequest(BaseModel):
    school_id: str = Field(..., min_length=1)


class RemoveMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
