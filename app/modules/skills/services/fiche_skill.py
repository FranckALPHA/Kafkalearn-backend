"""
services/fiche_skill.py
=======================
Génération de fiches de révision.
"""
import logging
import time

from app.modules.skills.services.base_skill import BaseSkill, SkillRequest, SkillResult

logger = logging.getLogger(__name__)


class FicheSkill(BaseSkill):
    """Génération de fiches de révision structurées."""

    async def run(self, request: SkillRequest) -> SkillResult:
        start_ms = time.time() * 1000

        matiere = request.params.get("matiere")
        niveau = request.params.get("niveau")
        notion = request.params.get("notion")
        nb_pages = min(request.params.get("nb_pages", 2), 5)

        # RAG pour le contenu pédagogique
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
        Tu es un rédacteur de fiches de révision pour élèves camerounais.

        Tâche: Crée une fiche de révision structurée sur le sujet demandé.

        Structure de la fiche ({nb_pages} page(s) max):
        1. 📋 Résumé du cours (définitions, théorèmes, formules)
        2. 💡 Méthodes et astuces à retenir
        3. 📝 Exemples types commentés
        4. ⚠️ Erreurs fréquentes à éviter
        5. 🔗 Pour aller plus loin

        Matière: {matiere or 'non spécifiée'}, Niveau: {niveau or 'non spécifié'}
        Notion: {notion or request.prompt}
        Langue: {request.langue}
        """

        user_prompt = f"{contexte}\n\nSujet de la fiche: {request.prompt}"

        result = await self.llm_generer(
            prompt=user_prompt,
            system_instruction=system_prompt,
            temperature=0.5,
            historique=request.historique_session,
            langue=request.langue,
        )

        latence_ms = int(time.time() * 1000 - start_ms)

        if result.get("error_code"):
            return SkillResult(
                success=False,
                skill_type="fiche",
                output_type="text",
                erreur_code=result["error_code"],
                latence_ms=latence_ms,
            )

        # Conversion Markdown → PDF async via Celery
        try:
            from app.modules.skills.jobs.tasks import generate_fiche_pdf_task
            generate_fiche_pdf_task.delay(
                user_id=request.user_id,
                message_id=0,  # Sera mis à jour après création du message
                contenu_markdown=llm_result.get("text", ""),
                metadata={
                    "titre": f"Fiche: {notion or request.prompt[:50]}",
                    "matiere": matiere,
                    "niveau": niveau,
                },
            )
        except Exception:
            pass  # PDF généré en arrière-plan, pas bloquant
        return SkillResult(
            success=True,
            skill_type="fiche",
            output_type="text",
            data={
                "titre": f"Fiche: {notion or request.prompt[:50]}",
                "matiere": matiere,
                "niveau": niveau,
                "notion": notion,
                "nb_pages_estimate": nb_pages,
            },
            quota_consomme=True,
            latence_ms=latence_ms,
            rag_chunks_utilises=len(chunks),
        )
