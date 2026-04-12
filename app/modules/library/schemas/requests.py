from pydantic import BaseModel, Field
from typing import Optional


class AssetShareRequest(BaseModel):
    is_public: bool = False


class AssetUpdateRequest(BaseModel):
    titre: Optional[str] = Field(None, max_length=255)
    subject: Optional[str] = Field(None, max_length=100)
    class_name: Optional[str] = Field(None, max_length=50)
    serie: Optional[str] = Field(None, max_length=20)
    notion: Optional[str] = Field(None, max_length=255)


class AssetCopyRequest(BaseModel):
    asset_id: int = Field(..., gt=0)


class AssetRatingRequest(BaseModel):
    note: int = Field(..., ge=1, le=5)
    commentaire: Optional[str] = Field(None, max_length=500)
