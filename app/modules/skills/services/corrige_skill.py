"""
services/corrige_skill.py
=========================
Génération de corrigés détaillés d'épreuves.
"""
import logging
import time

from app.modules.skills.services.base_skill import BaseSkill, SkillRequest, SkillResult

logger = logging.getLogger(__name__)


class CorrigeSkill(BaseSkill):
    """Génère des corrigés détaillés d'épreuves existantes."""

    async def run(self, request: SkillRequest) -> SkillResult:
        start_ms = time.time() * 1000

        matiere = request.params.get("matiere")
        niveau = request.params.get("niveau")
        annee = request.params.get("annee")

        # Charger le contexte RAG pour trouver l'épreuve
        chunks = []
        if request.avec_rag:
            chunks = await self.charger_contexte_rag(
                prompt=request.prompt,
                matiere=matiere,
                niveau=niveau,
                user_document_id=request.user_document_id,
                top_k=10,
            )

        contexte = self.formater_chunks_pour_prompt(chunks) if chunks else ""

        system_prompt = f"""
        Tu es un correcteur d'épreuves pour le système éducatif camerounais.

        Tâche: Fournis un corrigé DÉTAILLÉ avec barème pour chaque exercice.

        Format:
        - Pour chaque exercice: énoncé rappelé → résolution → barème
        - Explications pédagogiques pour les erreurs fréquentes
        - Matière: {matiere or 'non spécifiée'}, Niveau: {niveau or 'non spécifié'}
        - Langue: {request.langue}
        """

        user_prompt = f"{contexte}\n\nÉpreuve à corriger: {request.prompt}"

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
                skill_type="corrige",
                output_type="text",
                erreur_code=result["error_code"],
                latence_ms=latence_ms,
            )

        return SkillResult(
            success=True,
            skill_type="corrige",
            output_type="text",
            data={
                "titre": f"Corrigé {matiere} {niveau}",
                "matiere": matiere,
                "annee": annee,
            },
            quota_consomme=True,
            latence_ms=latence_ms,
            rag_chunks_utilises=len(chunks),
        )
