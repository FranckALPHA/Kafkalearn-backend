"""
services/epreuve_skill.py
=========================
Génération de sujets d'examen originaux.
"""
import logging
import time

from app.modules.skills.services.base_skill import BaseSkill, SkillRequest, SkillResult

logger = logging.getLogger(__name__)


class EpreuveSkill(BaseSkill):
    """Génère des sujets d'examen originaux conformes au programme."""

    async def run(self, request: SkillRequest) -> SkillResult:
        start_ms = time.time() * 1000

        matiere = request.params.get("matiere")
        niveau = request.params.get("niveau")
        serie = request.params.get("serie")
        duree = request.params.get("duree", "3h")
        coefficient = request.params.get("coefficient", 3)

        # RAG pour les programmes officiels
        chunks = []
        if request.avec_rag:
            chunks = await self.charger_contexte_rag(
                prompt=request.prompt,
                matiere=matiere,
                niveau=niveau,
                top_k=8,
            )

        contexte = self.formater_chunks_pour_prompt(chunks) if chunks else ""

        system_prompt = f"""
        Tu es un concepteur d'épreuves pour le système éducatif camerounais.

        Tâche: Crée un sujet d'examen ORIGINAL et conforme au programme.

        Format officiel:
        - République du Cameroun (en-tête)
        - Matière: {matiere}, Classe: {niveau}, Série: {serie or 'toutes'}
        - Durée: {duree}, Coefficient: {coefficient}
        - 3-4 exercices progressifs
        - Barème détaillé pour chaque exercice
        - Langue: {request.langue}
        """

        user_prompt = f"{contexte}\n\nSujet demandé: {request.prompt}"

        result = await self.llm_generer(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.8,
            historique=request.historique_session,
            langue=request.langue,
        )

        latence_ms = int(time.time() * 1000 - start_ms)

        if result.get("error_code"):
            return SkillResult(
                success=False,
                skill_type="epreuve",
                output_type="text",
                erreur_code=result["error_code"],
                latence_ms=latence_ms,
            )

        return SkillResult(
            success=True,
            skill_type="epreuve",
            output_type="text",
            data={
                "titre": f"Épreuve {matiere} {niveau} {serie}",
                "matiere": matiere,
                "niveau": niveau,
                "serie": serie,
            },
            quota_consomme=True,
            latence_ms=latence_ms,
            rag_chunks_utilises=len(chunks),
        )
