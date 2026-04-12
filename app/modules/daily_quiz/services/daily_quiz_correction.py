import logging
import uuid
from sqlalchemy.orm import Session
from redis import Redis

from app.modules.daily_quiz.services.base import DailyQuizBaseService
from app.modules.daily_quiz.models import DailyQuiz, DailyQuizAttempt

logger = logging.getLogger(__name__)


class DailyQuizCorrectionService(DailyQuizBaseService):
    async def corriger_tentative(
        self,
        user_id: uuid.UUID,
        quiz_id: int,
        reponses_user: list,
        duree_secondes: int,
        langue: str = "fr",
    ) -> dict:
        """Correct a quiz attempt and return results."""
        quiz = (
            self.db.query(DailyQuiz)
            .filter(DailyQuiz.id == quiz_id)
            .first()
        )
        if not quiz:
            raise ValueError(f"Quiz {quiz_id} not found")

        # Check no existing attempt for this user+quiz
        existing_attempt = (
            self.db.query(DailyQuizAttempt)
            .filter(
                DailyQuizAttempt.user_id == user_id,
                DailyQuizAttempt.daily_quiz_id == quiz_id,
            )
            .first()
        )
        if existing_attempt:
            raise ValueError("User has already submitted an attempt for this quiz")

        # Get reference questions
        ref_questions = quiz.get_questions_for_langue(langue, include_answers=True)

        # Correct answers
        score = 0
        total = len(ref_questions)
        correction_details = []

        for i, ref_q in enumerate(ref_questions):
            user_answer = reponses_user[i].get("reponse", "") if i < len(reponses_user) else ""
            is_correct = self._check_answer(ref_q, user_answer)
            if is_correct:
                score += 1
            correction_details.append({
                "question_index": i,
                "enonce": ref_q.get("enonce"),
                "user_answer": user_answer,
                "correct_answer": ref_q.get("bonne_reponse"),
                "is_correct": is_correct,
                "explication": ref_q.get("explication"),
            })

        score_pct = (score / total * 100) if total > 0 else 0.0

        # Save attempt
        attempt = DailyQuizAttempt(
            user_id=user_id,
            daily_quiz_id=quiz_id,
            score=score,
            score_pourcentage=score_pct,
            reponses_json=reponses_user,
            duree_secondes=duree_secondes,
            langue=langue,
            is_complete=len(reponses_user) >= total,
        )
        self.db.add(attempt)

        # Update quiz stats
        quiz.nb_tentatives = (quiz.nb_tentatives or 0) + 1
        if quiz.score_moyen is not None:
            quiz.score_moyen = (quiz.score_moyen + score_pct) / 2
        else:
            quiz.score_moyen = score_pct

        # Update leaderboard
        try:
            from app.modules.daily_quiz.services.leaderboard_service import LeaderboardService
            from datetime import datetime
            leaderboard_svc = LeaderboardService(self.db, self.redis)
            month_year = datetime.now().strftime("%Y-%m")
            await leaderboard_svc.mettre_a_jour_score(user_id, score_pct, month_year)
        except Exception as exc:
            logger.error("Failed to update leaderboard: %s", exc)

        # Update streak
        try:
            from app.modules.daily_quiz.services.quiz_streak_service import QuizStreakService
            streak_svc = QuizStreakService(self.db, self.redis)
            streak = await streak_svc.calculer_streak_quiz(user_id)
        except Exception as exc:
            logger.error("Failed to calculate streak: %s", exc)
            streak = 0

        self.db.commit()

        coaching_msg = self._generer_message_coaching(score_pct, quiz.theme)

        return {
            "score": score,
            "score_pourcentage": score_pct,
            "correction": correction_details,
            "streak": streak,
            "message_coaching": coaching_msg,
        }

    def _check_answer(self, question_ref: dict, user_answer: str) -> bool:
        """Normalize and compare user answer with reference answer."""
        bonne_reponse = question_ref.get("bonne_reponse", "")
        if isinstance(bonne_reponse, bool):
            # Handle true/false
            user_bool = str(user_answer).strip().lower() in ("true", "vrai", "yes", "oui", "1")
            return user_bool == bonne_reponse
        # Normalize string comparison
        return (
            str(user_answer).strip().lower()
            == str(bonne_reponse).strip().lower()
        )

    def _generer_message_coaching(self, score_pct: float, theme: str) -> str:
        """Generate a coaching message based on the score percentage."""
        if score_pct >= 90:
            return f"Excellent! Vous maitrisez parfaitement le theme '{theme}'. Continuez ainsi!"
        elif score_pct >= 70:
            return f"Tres bon resultat sur '{theme}'! Quelques revisions et vous serez parfait."
        elif score_pct >= 50:
            return f"Bon effort sur '{theme}'. Revoyez les points faibles pour progresser."
        elif score_pct >= 30:
            return f"Resultat mitigee sur '{theme}'. N'hesitez pas a relire le cours correspondant."
        else:
            return f"Le theme '{theme}' semble difficile. Prenez le temps de revisionner et reessayez demain!"
