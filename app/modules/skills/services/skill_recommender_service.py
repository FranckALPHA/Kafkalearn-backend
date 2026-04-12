"""
services/skill_recommender_service.py
=====================================
Recommandation de skills basée sur le profil d'apprentissage.
"""
import logging
from typing import Dict, Any, List

from app.modules.skills.services.base import SkillsBaseService

logger = logging.getLogger(__name__)


class SkillRecommenderService(SkillsBaseService):
    """Recommande des skills pertinents selon le profil utilisateur."""

    async def recommander_pour_session(
        self, user_id: str, matiere: str, sujet_session: str = None
    ) -> Dict[str, Any]:
        """
        Recommande un skill pertinent pour une session d'étude
        basé sur le profil d'apprentissage et les lacunes détectées.
        """
        from app.modules.users.models import UserLearningProfile
        from uuid import UUID

        # Lecture du profil pour personnalisation
        try:
            profile = (
                self.db.query(UserLearningProfile)
                .filter(UserLearningProfile.user_id == UUID(user_id))
                .first()
            )
        except Exception:
            profile = None

        # Logique basée sur les lacunes et l'historique
        if profile and profile.lacunes and matiere in profile.lacunes:
            return {
                "skill": "fiche",
                "raison": f"Tu as des lacunes en {matiere}. Une fiche de révision t'aidera.",
                "prompt_suggere": f"Fiche de révision sur {sujet_session or matiere}",
            }

        return {
            "skill": "quiz",
            "raison": f"Teste tes connaissances en {matiere}",
            "prompt_suggere": f"Quiz sur {sujet_session or matiere}",
        }

    async def recommander_apres_search(
        self, user_id: str, matiere: str, intention: str
    ) -> List[Dict[str, Any]]:
        """Recommande des skills après une recherche."""
        recs = []

        if intention == "explication":
            recs.append({
                "skill": "fiche",
                "raison": "Approfondis avec une fiche de révision",
                "prompt_suggere": f"Fiche complète sur {matiere}",
            })
        elif intention == "entrainement":
            recs.append({
                "skill": "quiz",
                "raison": "Teste-toi avec un quiz",
                "prompt_suggere": f"Quiz {matiere}",
            })

        recs.append({
            "skill": "tuteur",
            "raison": "Pose tes questions à un tuteur IA",
            "prompt_suggere": f"Explique-moi {matiere}",
        })

        return recs
