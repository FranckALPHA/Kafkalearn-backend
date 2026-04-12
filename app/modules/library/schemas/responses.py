from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class AssetListResponse(BaseModel):
    total: int
    page: int
    limit: int
    assets: List[Dict[str, Any]]


class AssetDetailResponse(BaseModel):
    id: int
    titre: str
    asset_type: str
    subject: Optional[str] = None
    class_name: Optional[str] = None
    serie: Optional[str] = None
    notion: Optional[str] = None
    langue: str
    is_public: bool
    nb_vues: int
    nb_telechargements: int
    nb_copies: int
    note_moyenne: Optional[float] = None
    nb_notes: int
    generation_status: str
    file_url: Optional[str] = None
    content_json: Optional[Dict[str, Any]] = None
    required_plan: Optional[str] = None
    lien_partage: Optional[str] = None
    is_owner: bool = False
    ma_note: Optional[int] = None
    created_at: Optional[str] = None


class PublicAssetListResponse(BaseModel):
    total: int
    page: int
    limit: int
    assets: List[Dict[str, Any]]


class ShareCodeResponse(BaseModel):
    is_public: bool
    lien_partage: Optional[str] = None
    url_complete: Optional[str] = None


class CommunityExploreResponse(BaseModel):
    total: int
    page: int
    limit: int
    assets: List[Dict[str, Any]]


class LibraryStatsResponse(BaseModel):
    total_assets: int
    assets_publics: int
    assets_par_type: Dict[str, int]
    assets_gener_7j: int
    taux_partage: float
    top_assets: List[Dict[str, Any]]
