"""
services/visualisation_skill.py
==============================
Génération de diagrammes et graphes.
"""
import logging
import time

from app.modules.skills.services.base_skill import BaseSkill, SkillRequest, SkillResult

logger = logging.getLogger(__name__)


class VisualisationSkill(BaseSkill):
    """Génère des visualisations (descriptions pour graphes/diagrammes)."""

    async def run(self, request: SkillRequest) -> SkillResult:
        start_ms = time.time() * 1000

        matiere = request.params.get("matiere")
        type_visualisation = request.params.get("type", "diagramme")

        system_prompt = f"""
        Tu es un générateur de visualisations pédagogiques.

        Tâche: Décris en détail le graphe/diagramme demandé avec:
        - Type de visualisation adapté ({type_visualisation})
        - Données à afficher (axes, légendes, valeurs)
        - Interprétation pédagogique
        - Matière: {matiere or 'non spécifiée'}
        - Langue: {request.langue}

        Si c'est une fonction mathématique, donne:
        - Tableau de variations
        - Points remarquables
        - Allure de la courbe
        """

        result = await self.llm_generer(
            prompt=request.prompt,
            system_instruction=system_prompt,
            temperature=0.5,
            historique=request.historique_session,
            langue=request.langue,
        )

        latence_ms = int(time.time() * 1000 - start_ms)

        if result.get("error_code"):
            return SkillResult(
                success=False,
                skill_type="visualisation",
                output_type="text",
                erreur_code=result["error_code"],
                latence_ms=latence_ms,
            )

        # TODO: Ajouter génération d'image réelle avec matplotlib/plotly
        return SkillResult(
            success=True,
            skill_type="visualisation",
            output_type="text",
            data={
                "titre": f"Visualisation: {request.prompt[:50]}",
                "matiere": matiere,
                "type": type_visualisation,
            },
            quota_consomme=True,
            latence_ms=latence_ms,
        )
