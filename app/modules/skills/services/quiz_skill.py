"""
services/quiz_skill.py
======================
Génération de quiz interactifs avec correction automatique.
"""
import json
import logging
import time
from typing import Dict, Any

from app.modules.skills.services.base_skill import BaseSkill, SkillRequest, SkillResult
from app.modules.skills.utils.json_validator import validate_quiz_json

logger = logging.getLogger(__name__)


class QuizSkill(BaseSkill):
    """Génération de quiz interactifs avec correction automatique."""

    async def run(self, request: SkillRequest) -> SkillResult:
        start_ms = time.time() * 1000

        # ─── 1. Extraction paramètres ────────────────────────────
        params = request.params
        nb_questions = min(params.get("nb_questions", 10), 20)
        type_quiz = params.get("type_quiz", "qcm")
        difficulte = params.get("difficulte", "moyen")
        matiere = params.get("matiere")
        niveau = params.get("niveau")
        notion = params.get("notion")

        # ─── 2. Chargement contexte RAG ──────────────────────────
        chunks = []
        if request.avec_rag:
            chunks = await self.charger_contexte_rag(
                prompt=request.prompt,
                matiere=matiere,
                niveau=niveau,
                user_document_id=request.user_document_id,
                top_k=8,
            )

        contexte_formate = self.formater_chunks_pour_prompt(chunks) if chunks else ""

        # ─── 3. Construction prompt JSON-strict ──────────────────
        system_prompt = f"""
        Tu es un générateur de quiz pédagogiques pour élèves camerounais.

        Tâche: Génère EXACTEMENT {nb_questions} questions de type {type_quiz}
        sur le sujet: {notion or request.prompt}
        Niveau: {niveau or 'non spécifié'}, Matière: {matiere or 'non spécifiée'}

        Format de sortie JSON STRICT (aucun texte autour):
        {{
          "quiz_id": "uuid-placeholder",
          "titre": "Quiz {matiere} - {notion} {niveau}",
          "matiere": "{matiere}",
          "niveau": "{niveau}",
          "nb_questions": {nb_questions},
          "type": "{type_quiz}",
          "questions": [
            {{
              "id": 0,
              "enonce": "Question claire et concise",
              "options": ["A", "B", "C", "D"],
              "bonne_reponse": "A",
              "explication": "Explication pédagogique courte",
              "difficulte": "{difficulte}"
            }}
          ]
        }}

        Règles:
        - Questions adaptées au niveau {niveau}
        - Explications pédagogiques, pas juste la réponse
        - Une seule bonne réponse pour qcm
        - Langue: {request.langue}
        """

        user_prompt = f"{contexte_formate}\n\nGénère le quiz maintenant en JSON strict."

        # ─── 4. Appel LLM avec retry sur JSON invalide ───────────
        max_retries = 3
        quiz_data = None

        for attempt in range(max_retries):
            result = await self.llm_generer(
                prompt=user_prompt,
                system_instruction=system_prompt,
                temperature=0.7,
                historique=request.historique_session,
                langue=request.langue,
                response_format="json",
            )

            if result.get("error_code"):
                return SkillResult(
                    success=False,
                    skill_type="quiz",
                    output_type="json",
                    erreur_code=result["error_code"],
                    latence_ms=int(time.time() * 1000 - start_ms),
                )

            try:
                quiz_data = json.loads(result["text"])
                is_valid, errors = validate_quiz_json(quiz_data, type_quiz, nb_questions)

                if is_valid:
                    break
                elif attempt < max_retries - 1:
                    user_prompt = f"Le JSON précédent avait des erreurs: {errors}. Corrige et renvoie le JSON complet."
                else:
                    return SkillResult(
                        success=False,
                        skill_type="quiz",
                        output_type="json",
                        erreur_code="JSON_VALIDATION_FAILED",
                        latence_ms=int(time.time() * 1000 - start_ms),
                    )
            except json.JSONDecodeError:
                if attempt < max_retries - 1:
                    user_prompt = "Ta réponse n'était pas du JSON valide. Réessaie avec un JSON strict."
                else:
                    return SkillResult(
                        success=False,
                        skill_type="quiz",
                        output_type="json",
                        erreur_code="JSON_PARSE_ERROR",
                        latence_ms=int(time.time() * 1000 - start_ms),
                    )

        # ─── 5. Construction résultat ────────────────────────────
        latence_ms = int(time.time() * 1000 - start_ms)

        return SkillResult(
            success=True,
            skill_type="quiz",
            output_type="json",
            json_data=quiz_data,
            data={
                "titre": quiz_data.get("titre"),
                "nb_questions": quiz_data.get("nb_questions"),
                "matiere": quiz_data.get("matiere"),
            },
            quota_consomme=True,
            latence_ms=latence_ms,
            rag_chunks_utilises=len(chunks),
        )
