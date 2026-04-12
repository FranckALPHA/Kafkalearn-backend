from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class SchoolDashboardResponse(BaseModel):
    id: str
    nom: str
    ville: str
    region: Optional[str] = None
    code_invitation: Optional[str] = None
    nb_membres: int
    nb_eleves_max: int
    places_restantes: int
    date_expiration: Optional[str] = None
    jours_restants: int
    is_active: bool
    is_trial: bool
    engagement: Optional[Dict[str, Any]] = None
    quota_ia: Optional[Dict[str, Any]] = None
    tarif: Optional[Dict[str, Any]] = None
    is_admin: bool = False


class MemberListResponse(BaseModel):
    total: int
    page: int
    limit: int
    membres: List[Dict[str, Any]]


class PricingResponse(BaseModel):
    tarifs: List[Dict[str, Any]]
    essai_gratuit_jours: int = 30
    devise: str = "FCFA (XAF)"


class SchoolInvitationResult(BaseModel):
    nb_lignes_total: int
    nb_ajoutes: int
    nb_existants: int
    nb_erreurs: int
    erreurs: List[Dict[str, Any]] = []
    places_restantes_apres: int
