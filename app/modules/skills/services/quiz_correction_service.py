"""
services/quiz_correction_service.py
===================================
Correction de quiz avec feedback détaillé et détection de lacunes.
"""
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.skills.models import QuizSession
from app.modules.skills.services.base import SkillsBaseService

logger = logging.getLogger(__name__)


class QuizCorrectionService(SkillsBaseService):
    """Correction de quiz et analyse des résultats."""

    async def corriger(
        self,
        quiz_session_id: str,
        reponses_utilisateur: Dict[int, str],
        duree_secondes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Corrige les réponses d'un quiz et retourne le résultat détaillé.

        Args:
            quiz_session_id: ID de la session quiz
            reponses_utilisateur: {question_id: réponse_utilisateur}
            duree_secondes: temps mis pour répondre

        Returns:
            Dict avec score, corrections, lacunes détectées
        """
        from uuid import UUID

        session_id = UUID(quiz_session_id)
        quiz_session = (
            self.db.query(QuizSession)
            .filter(QuizSession.id == session_id)
            .first()
        )

        if not quiz_session:
            raise ValueError(f"Quiz session {quiz_session_id} not found")

        if quiz_session.is_submitted:
            raise ValueError("Quiz already submitted")

        questions = quiz_session.questions or []
        nb_bonnes = 0
        nb_mauvaises = 0
        corrections = []
        notions_rates = {}

        for question in questions:
            q_id = question.get("id")
            bonne_reponse = question.get("bonne_reponse")
            reponse_user = reponses_utilisateur.get(q_id)
            est_correct = reponse_user == bonne_reponse

            if est_correct:
                nb_bonnes += 1
            else:
                nb_mauvaises += 1
                # Track notions problématiques
                notion = question.get("notion", "general")
                notions_rates[notion] = notions_rates.get(notion, 0) + 1

            corrections.append({
                "question_id": q_id,
                "enonce": question.get("enonce"),
                "reponse_utilisateur": reponse_user,
                "bonne_reponse": bonne_reponse,
                "est_correct": est_correct,
                "explication": question.get("explication", ""),
            })

        # Calcul du score
        total = nb_bonnes + nb_mauvaises
        score_percent = round((nb_bonnes / total) * 100, 1) if total > 0 else 0

        # Détection des lacunes (notions avec > 50% d'erreurs)
        lacunes = [
            {"notion": notion, "erreurs": count}
            for notion, count in notions_rates.items()
            if count >= 2  # au moins 2 erreurs sur la même notion
        ]

        # Mise à jour de la session
        quiz_session.reponses_utilisateur = reponses_utilisateur
        quiz_session.nb_bonnes_reponses = nb_bonnes
        quiz_session.nb_mauvaises_reponses = nb_mauvaises
        quiz_session.score_percent = score_percent
        quiz_session.submitted_at = func.now()
        quiz_session.duree_secondes = duree_secondes
        quiz_session.lacunes_detectees = lacunes if lacunes else None

        self.db.commit()

        # Détection de la lacune principale
        lacune_principale = None
        if lacunes:
            lacune_principale = max(lacunes, key=lambda x: x["erreurs"])["notion"]

        return {
            "quiz_session_id": str(quiz_session.id),
            "score_percent": score_percent,
            "nb_bonnes_reponses": nb_bonnes,
            "nb_mauvaises_reponses": nb_mauvaises,
            "is_passing": score_percent >= 50,
            "corrections": corrections,
            "duree_secondes": duree_secondes,
            "lacunes_detectees": lacunes,
            "lacune_detectee": lacune_principale,
            "matiere": quiz_session.matiere,
        }
