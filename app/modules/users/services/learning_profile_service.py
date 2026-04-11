"""
services/learning_profile_service.py
====================================
Service pour la gestion du profil cognitif d'apprentissage.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.users.models import UserLearningProfile
from app.modules.users.utils.cache import cache_result
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)

MAX_HISTORIQUE_SIZE = 100
MAX_INTENTIONS_SIZE = 20


class LearningProfileService(BaseService):
    """Service pour gerer le profil d'apprentissage d'un utilisateur."""

    @cache_result(key_prefix="user:learning-profile", ttl_seconds=300)
    async def obtenir_profil_complet(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne le profil d'apprentissage complet d'un utilisateur.

        Args:
            user_id: UUID de l'utilisateur.

        Returns:
            Dictionnaire contenant toutes les donnees du profil, ou None.
        """
        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )

        if not profile:
            return None

        return {
            "id": profile.id,
            "user_id": str(profile.user_id),
            "historique_recherches": profile.historique_recherches or [],
            "lacunes": profile.lacunes or {},
            "forces": profile.forces or {},
            "interets": profile.interets or [],
            "matieres_frequentes": profile.matieres_frequentes or {},
            "intentions_recentes": profile.intentions_recentes or [],
            "skills_utilises": profile.skills_utilises or {},
            "sujets_vus": profile.sujets_vus or [],
            "heures_actives": profile.heures_actives or {},
            "jours_actifs": profile.jours_actifs or {},
            "score_par_matiere": profile.score_par_matiere or {},
            "last_wisdom_id": profile.last_wisdom_id,
            "dernier_rapport_at": (
                profile.dernier_rapport_at.isoformat() if profile.dernier_rapport_at else None
            ),
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }

    def ajouter_recherche(
        self,
        user_id: str,
        requete: str,
        intention: Optional[str] = None,
        matiere: Optional[str] = None,
        notion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ajoute une recherche a l'historique (FIFO 100) et met a jour
        les matieres frequentes.

        Args:
            user_id: UUID de l'utilisateur.
            requete: Texte de la recherche.
            intention: Intention detectee (ex: "revision", "approfondissement").
            matiere: Matiere concernee.
            notion: Notion specifique recherchee.

        Returns:
            Le profil mis a jour (partiel).

        Raises:
            ValueError: Si le profil n'existe pas.
        """
        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )
        if not profile:
            raise ValueError("LEARNING_PROFILE_NOT_FOUND")

        # Ajouter la recherche a l'historique (FIFO 100)
        historique = profile.historique_recherches or []
        entree = {
            "requete": requete,
            "intention": intention,
            "matiere": matiere,
            "notion": notion,
            "timestamp": datetime.utcnow().isoformat(),
        }
        historique.append(entree)
        if len(historique) > MAX_HISTORIQUE_SIZE:
            historique = historique[-MAX_HISTORIQUE_SIZE:]
        profile.historique_recherches = historique

        # Mettre a jour les matieres frequentes
        matieres_freq = profile.matieres_frequentes or {}
        if matiere:
            matieres_freq[matiere] = matieres_freq.get(matiere, 0) + 1
        profile.matieres_frequentes = matieres_freq

        # Mettre a jour les intentions recentes (FIFO 20)
        if intention:
            intentions = profile.intentions_recentes or []
            intentions.append({
                "intention": intention,
                "timestamp": datetime.utcnow().isoformat(),
            })
            if len(intentions) > MAX_INTENTIONS_SIZE:
                intentions = intentions[-MAX_INTENTIONS_SIZE:]
            profile.intentions_recentes = intentions

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        return {
            "historique_count": len(historique),
            "matieres_frequentes": matieres_freq,
        }

    def enregistrer_score_quiz(
        self,
        user_id: str,
        matiere: str,
        score: float,
        lacune_notion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enregistre le score d'un quiz et met a jour les lacunes/forces.

        Args:
            user_id: UUID de l'utilisateur.
            matiere: Matiere du quiz.
            score: Score obtenu (0-100).
            lacune_notion: Notion identifiee comme lacune (si score faible).

        Returns:
            Dictionnaire avec les scores et lacunes mis a jour.

        Raises:
            ValueError: Si le profil n'existe pas.
        """
        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )
        if not profile:
            raise ValueError("LEARNING_PROFILE_NOT_FOUND")

        # Mettre a jour le score par matiere (moyenne mobile)
        scores = profile.score_par_matiere or {}
        ancien_score = scores.get(matiere, {})
        if isinstance(ancien_score, dict):
            count = ancien_score.get("count", 0) + 1
            old_avg = ancien_score.get("avg", 0)
            new_avg = ((old_avg * (count - 1)) + score) / count if count > 0 else score
            scores[matiere] = {"avg": round(new_avg, 2), "count": count}
        else:
            scores[matiere] = {"avg": score, "count": 1}
        profile.score_par_matiere = scores

        # Mettre a jour les lacunes (score < 50%)
        lacunes = profile.lacunes or {}
        forces = profile.forces or {}

        if score < 50:
            lacunes_mat = lacunes.get(matiere, [])
            if lacune_notion and lacune_notion not in lacunes_mat:
                lacunes_mat.append(lacune_notion)
            lacunes[matiere] = lacunes_mat
            # Retirer des forces si present
            forces.pop(matiere, None)
        elif score >= 75:
            forces[matiere] = {
                "score": score,
                "last_updated": datetime.utcnow().isoformat(),
            }
            # Retirer des lacunes si present
            lacunes.pop(matiere, None)

        profile.lacunes = lacunes
        profile.forces = forces

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        return {
            "score_par_matiere": scores,
            "lacunes": lacunes,
            "forces": forces,
        }
