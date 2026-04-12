from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class CheckoutResponse(BaseModel):
    authorization_url: str
    reference: str
    montant: int
    currency: str
    plan_id: str
    expires_at: Optional[str] = None


class TransactionHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    transactions: List[Dict[str, Any]]


class PlanListResponse(BaseModel):
    plans: List[Dict[str, Any]]
    devise: str = "FCFA"


class SubscriptionStatusResponse(BaseModel):
    plan_base: str
    plan_effectif: str
    plan_expiration_at: Optional[str] = None
    jours_restants: int
    quota_ia: Dict[str, Any]
    auto_renew: bool = False
    source: str = "payment_direct"
