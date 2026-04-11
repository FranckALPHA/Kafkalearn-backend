"""
services/skill_recommender_service.py
=====================================
Recommandation proactive de skills basée sur le profil utilisateur.
"""
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.modules.skills.services.base import SkillsBaseService

logger = logging.getLogger(__name__)


class SkillRecommenderService(SkillsBaseService):
    """Recommande des skills pertinents selon le contexte."""

    def recommander_pour_session(
        self,
        user_id: str,
        matiere: str,
        sujet_session: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recommande un skill pertinent pour une session d'étude.

        Returns:
            {"skill": "quiz", "raison": "...", "prompt_suggere": "..."}
        """
        # TODO: Implémenter une vraie logique basée sur le profil
        # Pour l'instant, recommandations basiques
        recommendations = {
            "quiz": {
                "skill": "quiz",
                "raison": f"Teste tes connaissances en {matiere}",
                "prompt_suggere": f"Quiz sur {sujet_session or matiere}",
            },
            "fiche": {
                "skill": "fiche",
                "raison": f"Révise les concepts clés de {matiere}",
                "prompt_suggere": f"Fiche de révision sur {sujet_session or matiere}",
            },
            "solver": {
                "skill": "solver",
                "raison": f"Résous des problèmes de {matiere}",
                "prompt_suggere": f"Résous ce problème de {matiere}: {sujet_session or ''}",
            },
        }

        # Par défaut: recommander quiz
        return recommendations["quiz"]

    def recommander_apres_search(
        self,
        user_id: str,
        matiere: str,
        intention: str,
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
