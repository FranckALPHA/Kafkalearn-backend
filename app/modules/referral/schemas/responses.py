from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ReferralStatsResponse(BaseModel):
    referral_code: str
    referral_link: str
    nb_filleuls_total: int
    nb_filleuls_actifs: int
    has_referrer: bool
    referrer_prenom: Optional[str] = None
    cycle_actuel: int
    filleuls_dans_cycle_actuel: int
    filleuls_restants_pour_bonus: int
    prochain_bonus: Optional[Dict[str, Any]] = None
    recompenses_actives: List[Dict[str, Any]] = []
    liste_filleuls: List[Dict[str, Any]] = []


class LeaderboardResponse(BaseModel):
    leaderboard: List[Dict[str, Any]]


class RewardTiersResponse(BaseModel):
    description: str
    mecanisme: str
    paliers: List[Dict[str, Any]]
    definition_actif: str
