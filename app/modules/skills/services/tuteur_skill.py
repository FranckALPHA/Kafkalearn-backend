"""
services/tuteur_skill.py
========================
Agent conversationnel pédagogique universel.
"""
import logging
import time

from app.modules.skills.services.base_skill import BaseSkill, SkillRequest, SkillResult

logger = logging.getLogger(__name__)


class TuteurSkill(BaseSkill):
    """
    Tuteur IA conversationnel — fallback universel quand aucun skill
    spécifique n'est détecté.
    """

    async def run(self, request: SkillRequest) -> SkillResult:
        start_ms = time.time() * 1000

        matiere = request.params.get("matiere")
        niveau = request.params.get("niveau")

        system_prompt = f"""
        Tu es un tuteur pédagogique bienveillant pour élèves camerounais.

        Rôle:
        - Aide l'élève à comprendre le concept demandé
        - Pose des questions pour guider la réflexion
        - Donne des exemples concrets adaptés au contexte camerounais
        - Encourage et valorise les progrès
        - Niveau: {niveau or 'adaptatif'}
        - Langue: {request.langue}

        Si la question est vague, demande des précisions avant de répondre.
        """

        result = await self.llm_generer(
            prompt=request.prompt,
            system_instruction=system_prompt,
            temperature=0.7,
            historique=request.historique_session,
            langue=request.langue,
        )

        latence_ms = int(time.time() * 1000 - start_ms)

        if result.get("error_code"):
            return SkillResult(
                success=False,
                skill_type="tuteur",
                output_type="text",
                erreur_code=result["error_code"],
                latence_ms=latence_ms,
            )

        return SkillResult(
            success=True,
            skill_type="tuteur",
            output_type="text",
            data={
                "titre": "Session tutorat",
                "matiere": matiere,
            },
            quota_consomme=True,
            latence_ms=latence_ms,
        )
