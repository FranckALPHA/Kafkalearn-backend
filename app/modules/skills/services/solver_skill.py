"""
services/solver_skill.py
========================
Résolution pas-à-pas de problèmes mathématiques/scientifiques.
"""
import logging
import time
from typing import Dict, Any

from app.modules.skills.services.base_skill import BaseSkill, SkillRequest, SkillResult
from app.modules.skills.utils.math_evaluator import evaluate_expression

logger = logging.getLogger(__name__)


class SolverSkill(BaseSkill):
    """Résolution pas-à-pas de problèmes avec explications."""

    async def run(self, request: SkillRequest) -> SkillResult:
        start_ms = time.time() * 1000

        matiere = request.params.get("matiere")
        niveau = request.params.get("niveau")
        notion = request.params.get("notion")

        # Charger contexte RAG si pertinent
        chunks = []
        if request.avec_rag:
            chunks = await self.charger_contexte_rag(
                prompt=request.prompt,
                matiere=matiere,
                niveau=niveau,
                user_document_id=request.user_document_id,
                top_k=6,
            )

        contexte = self.formater_chunks_pour_prompt(chunks) if chunks else ""

        system_prompt = f"""
        Tu es un résolveur de problèmes pédagogiques pour élèves camerounais.

        Tâche: Résous le problème suivant ÉTAPE PAR ÉTAPE avec des explications claires.

        Règles:
        - Montre chaque étape de calcul explicitement
        - Explique le raisonnement à chaque étape
        - Utilise un langage adapté au niveau {niveau or 'non spécifié'}
        - Vérifie le résultat final
        - Si c'est une équation, montre la résolution complète
        - Langue: {request.langue}
        """

        user_prompt = f"{contexte}\n\nProblème à résoudre: {request.prompt}"

        result = await self.llm_generer(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.3,
            historique=request.historique_session,
            langue=request.langue,
        )

        latence_ms = int(time.time() * 1000 - start_ms)

        if result.get("error_code"):
            return SkillResult(
                success=False,
                skill_type="solver",
                output_type="text",
                erreur_code=result["error_code"],
                latence_ms=latence_ms,
            )

        return SkillResult(
            success=True,
            skill_type="solver",
            output_type="text",
            data={
                "titre": f"Résolution: {request.prompt[:50]}",
                "matiere": matiere,
                "notion": notion,
            },
            quota_consomme=True,
            latence_ms=latence_ms,
            rag_chunks_utilises=len(chunks),
        )
