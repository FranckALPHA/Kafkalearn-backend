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
        quiz = self.db.query(DailyQuiz).filter(DailyQuiz.id == quiz_id).first()
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
            user_answer = (
                reponses_user[i].get("reponse", "") if i < len(reponses_user) else ""
            )
            is_correct = self._check_answer(ref_q, user_answer)
            if is_correct:
                score += 1

            # Handle nested format (fr/en)
            if isinstance(ref_q, dict) and "fr" in ref_q:
                question_data = ref_q["fr"]
            elif isinstance(ref_q, dict) and "en" in ref_q:
                question_data = ref_q["en"]
            else:
                question_data = ref_q

            # Get correct answer from nested structure
            correct_answer = (
                question_data.get("answer")
                or question_data.get("bonne_reponse")
                or question_data.get("correct_answer")
                or question_data.get("correct_answer_index", "")
            )

            # Get question text - handle multiple formats
            enonce = (
                question_data.get("question")
                or question_data.get("question_fr")
                or question_data.get("question_en")
                or question_data.get("enonce")
                or question_data.get("text")
            )

            # Convert to human-readable format
            readable_correct = self._get_readable_answer(question_data, correct_answer)
            readable_user = self._get_readable_answer(question_data, user_answer)

            correction_details.append(
                {
                    "question_index": i,
                    "enonce": enonce,
                    "user_answer": readable_user,
                    "correct_answer": readable_correct,
                    "is_correct": is_correct,
                    "explication": question_data.get("explication")
                    or question_data.get("explanation_fr"),
                }
            )

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
            from app.modules.daily_quiz.services.leaderboard_service import (
                LeaderboardService,
            )
            from datetime import datetime

            leaderboard_svc = LeaderboardService(self.db, self.redis)
            month_year = datetime.now().strftime("%Y-%m")
            await leaderboard_svc.mettre_a_jour_score(user_id, score_pct, month_year)
        except Exception as exc:
            logger.error("Failed to update leaderboard: %s", exc)

        # Update streak
        try:
            from app.modules.daily_quiz.services.quiz_streak_service import (
                QuizStreakService,
            )

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

    def _get_readable_answer(self, question_data: dict, answer_value) -> str:
        """Convert answer to human-readable format."""
        if answer_value is None or answer_value == "":
            return ""

        # If answer is an index, convert to letter or get from options
        if isinstance(answer_value, int):
            options = question_data.get("options", {})
            # Handle nested options format {"A": {"fr": "...", "en": "..."}}
            if isinstance(options, dict):
                first_key = list(options.keys())[0] if options else None
                if first_key:
                    opt = options[first_key]
                    if isinstance(opt, dict):
                        return f"{chr(65 + answer_value)}: {opt.get('fr', opt.get('en', ''))}"
                    elif isinstance(opt, list) and 0 <= answer_value < len(opt):
                        return f"{chr(65 + answer_value)}: {opt[answer_value]}"
            elif isinstance(options, list) and 0 <= answer_value < len(options):
                return f"{chr(65 + answer_value)}: {options[answer_value]}"
            return chr(65 + answer_value)  # Just return A, B, C, D

        # If answer is a letter (A, B, C, D), try to get option text
        if isinstance(answer_value, str):
            answer_upper = answer_value.strip().upper()
            options = question_data.get("options", {})

            # Handle nested options format
            if isinstance(options, dict) and answer_upper in options:
                opt = options[answer_upper]
                if isinstance(opt, dict):
                    return f"{answer_upper}: {opt.get('fr', opt.get('en', ''))}"
                return f"{answer_upper}: {opt}"

            # Handle array options
            if isinstance(options, list) and answer_upper in options:
                idx = ord(answer_upper) - 65
                if 0 <= idx < len(options):
                    return f"{answer_upper}: {options[idx]}"

            return answer_upper

        return str(answer_value)

    def _check_answer(self, question_ref: dict, user_answer: str) -> bool:
        """Normalize and compare user answer with reference answer."""
        # Handle new nested format with 'fr' or 'en' keys
        if "fr" in question_ref:
            question_ref = question_ref["fr"]
        elif "en" in question_ref:
            question_ref = question_ref["en"]

        # Try different answer keys
        bonne_reponse = (
            question_ref.get("answer")
            or question_ref.get("bonne_reponse")
            or question_ref.get("correct_answer")
            or question_ref.get("correct_answer_index", "")
        )

        if bonne_reponse is None or bonne_reponse == "":
            return False

        if isinstance(bonne_reponse, bool):
            # Handle true/false
            user_bool = str(user_answer).strip().lower() in (
                "true",
                "vrai",
                "yes",
                "oui",
                "1",
            )
            return user_bool == bonne_reponse

        # If answer is an index (0, 1, 2, 3), convert to letter
        if isinstance(bonne_reponse, int):
            expected_index = bonne_reponse
            user_index = -1

            # Convert user answer to index
            user_answer_upper = str(user_answer).strip().upper()
            if user_answer_upper in ("A", "B", "C", "D", "E", "F"):
                user_index = ord(user_answer_upper) - 65
            elif user_answer_upper.isdigit() and 0 <= int(user_answer_upper) <= 9:
                user_index = int(user_answer_upper)

            return user_index == expected_index

        # If answer is a letter (A, B, C, D), compare with user answer
        if isinstance(bonne_reponse, str):
            expected = bonne_reponse.strip().upper()
            user = str(user_answer).strip().upper()

            # Direct match
            if user == expected:
                return True

            # Check if user answer matches the option text
            options = question_ref.get("options", [])
            for idx, opt in enumerate(options):
                opt_upper = str(opt).strip().upper()
                if user == opt_upper or user in opt_upper:
                    return True
                # Also check index match
                if user == chr(65 + idx):
                    return expected == chr(65 + idx)

            return False

        # Fallback
        return str(user_answer).strip().lower() == str(bonne_reponse).strip().lower()

    def _generer_message_coaching(self, score_pct: float, theme: str) -> str:
        """Generate a coaching message based on the score percentage."""
        if score_pct >= 90:
            return f"Excellent! Vous maitrisez parfaitement le theme '{theme}'. Continuez ainsi!"
        elif score_pct >= 70:
            return f"Tres bon resultat sur '{theme}'! Quelques revisions et vous serez parfait."
        elif score_pct >= 50:
            return (
                f"Bon effort sur '{theme}'. Revoyez les points faibles pour progresser."
            )
        elif score_pct >= 30:
            return f"Resultat mitigee sur '{theme}'. N'hesitez pas a relire le cours correspondant."
        else:
            return f"Le theme '{theme}' semble difficile. Prenez le temps de revisionner et reessayez demain!"
