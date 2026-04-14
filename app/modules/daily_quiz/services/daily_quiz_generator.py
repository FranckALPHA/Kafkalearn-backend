"""
services/daily_quiz_generator.py
=================================
Service métier pour le Quiz Quotidien.
Gère la génération via LLM, la soumission et les scores cumulés.
Pas de connexion au profil cognitif — feature standalone de culture générale.
"""
import json
import logging
import random
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.modules.daily_quiz.models import (
    DailyQuiz,
    DailyQuizAttempt,
    MonthlyLeaderboard,
)
from app.modules.users.models.user import User

log = logging.getLogger(__name__)

QUIZ_TYPES = ["qcm", "qro", "phrase_completion", "true_false", "ordering", "matching"]
QUIZ_TYPE_NAMES = {
    "qcm": "QCM",
    "qro": "QRO (Question à Réponse Ouverte)",
    "phrase_completion": "Phrase à compléter",
    "true_false": "Vrai / Faux",
    "ordering": "Classement / Ordonnancement",
    "matching": "Association / Correspondance",
}


def get_random_quiz_type() -> str:
    """Retourne un type de quiz aléatoire."""
    return random.choice(QUIZ_TYPES)


def get_quiz_type_of_the_day(target_date: date = None) -> str:
    """Retourne le type de quiz de manière aléatoire à chaque appel."""
    return get_random_quiz_type()


def get_prompt_for_type(quiz_type: str, target_date: date) -> tuple[str, str]:
    """Retourne le system_prompt et le prompt utilisateur pour un type de quiz donné."""

    if quiz_type == "qcm":
        system_prompt = (
            "Tu es un expert en culture générale moderne et technologique, avec une connaissance encyclopédique du Cameroun. "
            "Génère 5 questions QCM captivantes et variées en DEUX LANGUES : FRANÇAIS et ANGLAIS. "
            "Thématiques obligatoires (mélange équilibré) :\n"
            "1. Connaissance du Cameroun (Histoire, Géographie, Sports, Personnalités, Innovation locale).\n"
            "2. Nouvelles Technologies & IA (IA générative, futur du travail, gadgets, Internet).\n"
            "3. Culture Tech Africaine (Startups, impact du numérique au pays).\n"
            "Réponds UNIQUEMENT en JSON avec la structure :\n"
            '{"questions": {"fr": [{"id": 0, "text": "...", "options": ["A", "B", "C", "D"], "correct_answer_index": 0, "explanation": "..."}], "en": [{"id": 0, "text": "...", "options": ["A", "B", "C", "D"], "correct_answer_index": 0, "explanation": "..."}]}}'
        )
        user_prompt = f"Génère le Quiz Expert du jour ({target_date}). Mélange : 40% IA/Tech, 40% Cameroun, 20% Culture Générale. 5 questions QCM en français ET anglais. Chaque question doit avoir les deux versions linguistiques."

    elif quiz_type == "qro":
        system_prompt = (
            "Tu es un expert en culture générale moderne et technologique, avec une connaissance encyclopédique du Cameroun. "
            "Génère 5 questions à réponse ouverte captivantes et variées en DEUX LANGUES : FRANÇAIS et ANGLAIS. "
            "L'utilisateur doit rédiger une réponse courte (1-3 phrases). "
            "Thématiques obligatoires (mélange équilibrée) :\n"
            "1. Connaissance du Cameroun (Histoire, Géographie, Sports, Personnalités, Innovation locale).\n"
            "2. Nouvelles Technologies & IA (IA générative, futur du travail, gadgets, Internet).\n"
            "3. Culture Tech Africaine (Startups, impact du numérique au pays).\n"
            "Réponds UNIQUEMENT en JSON avec la structure :\n"
            '{"questions": {"fr": [{"id": 0, "text": "...", "expected_keyword": "mot_clé", "explanation": "..."}], "en": [{"id": 0, "text": "...", "expected_keyword": "keyword", "explanation": "..."}]}}'
        )
        user_prompt = f"Génère le Quiz du jour ({target_date}). 5 questions à réponse ouverte en français ET anglais. Chaque question doit avoir un mot-clé attendu pour la correction dans les deux langues."

    elif quiz_type == "phrase_completion":
        system_prompt = (
            "Tu es un expert en culture générale moderne et technologique, avec une connaissance encyclopédique du Cameroun. "
            "Génère 5 phrases à compléter captivantes et variées en DEUX LANGUES : FRANÇAIS et ANGLAIS. "
            "L'utilisateur doit remplir le mot manquant. "
            "Thématiques obligatoires (mélange équilibrée) :\n"
            "1. Connaissance du Cameroun (Histoire, Géographie, Sports, Personnalités, Innovation locale).\n"
            "2. Nouvelles Technologies & IA (IA générative, futur du travail, gadgets, Internet).\n"
            "3. Culture Tech Africaine (Startups, impact du numérique au pays).\n"
            "Réponds UNIQUEMENT en JSON avec la structure :\n"
            '{"questions": {"fr": [{"id": 0, "text": "...", "missing_word": "mot", "explanation": "explication"}], "en": [{"id": 0, "text": "...", "missing_word": "word", "explanation": "explanation"}]}}'
        )
        user_prompt = f"Génère le Quiz du jour ({target_date}). 5 phrases à compléter en français ET anglais avec un mot manquant dans les deux langues."

    elif quiz_type == "true_false":
        system_prompt = (
            "Tu es un expert en culture générale moderne et technologique, avec une connaissance encyclopédique du Cameroun. "
            "Génère 5 affirmations Vrai/Faux captivantes et variées en DEUX LANGUES : FRANÇAIS et ANGLAIS. "
            "L'utilisateur doit dire si l'affirmation est vraie ou fausse. "
            "Thématiques obligatoires (mélange équilibrée) :\n"
            "1. Connaissance du Cameroun (Histoire, Géographie, Sports, Personnalités, Innovation locale).\n"
            "2. Nouvelles Technologies & IA (IA générative, futur du travail, gadgets, Internet).\n"
            "3. Culture Tech Africaine (Startups, impact du numérique au pays).\n"
            "Réponds UNIQUEMENT en JSON avec la structure :\n"
            '{"questions": {"fr": [{"id": 0, "text": "...", "correct_answer": true, "explanation": "..."}], "en": [{"id": 0, "text": "...", "correct_answer": true, "explanation": "..."}]}}'
        )
        user_prompt = f"Génère le Quiz du jour ({target_date}). 5 affirmations Vrai/Faux en français ET anglais. true = affirmation correcte, false = affirmation fausse."

    elif quiz_type == "ordering":
        system_prompt = (
            "Tu es un expert en culture générale moderne et technologique, avec une connaissance encyclopédique du Cameroun. "
            "Génère 3 questions de classement/ordonnancement captivantes en DEUX LANGUES : FRANÇAIS et ANGLAIS. "
            "L'utilisateur doit ordonner les éléments du plus ancien au plus récent ou du plus important au moins important. "
            "Thématiques : Chronologie d'événements, Classement de pays par population, etc.\n"
            "Réponds UNIQUEMENT en JSON avec la structure :\n"
            '{"questions": {"fr": [{"id": 0, "description": "...", "text": "Classez ces éléments...", "items": [{"id": "A", "label": "..."}, {"id": "B", "label": "..."}], "correct_order": ["A", "B", ...], "explanation": "..."}], "en": [{"id": 0, "description": "...", "text": "Order these elements...", "items": [{"id": "A", "label": "..."}, {"id": "B", "label": "..."}], "correct_order": ["A", "B", ...], "explanation": "..."}]}}'
        )
        user_prompt = f"Génère le Quiz du jour ({target_date}). 3 questions de classement en français ET anglais. Chaque question doit avoir 4 éléments à ordonner."

    elif quiz_type == "matching":
        system_prompt = (
            "Tu es un expert en culture générale moderne et technologique, avec une connaissance encyclopédique du Cameroun. "
            "Génère 3 questions d'association/correspondance captivantes en DEUX LANGUES : FRANÇAIS et ANGLAIS. "
            "L'utilisateur doit faire correspondre les éléments de gauche avec ceux de droite. "
            "Thématiques : Villes et régions, Personnalités et domaines, Dates et événements, etc.\n"
            "Réponds UNIQUEMENT en JSON avec la structure :\n"
            '{"questions": {"fr": [{"id": 0, "description": "...", "text": "Associez...", "pairs": [{"left": "...", "right": "..."}], "explanation": "..."}], "en": [{"id": 0, "description": "...", "text": "Match...", "pairs": [{"left": "...", "right": "..."}], "explanation": "..."}]}}'
        )
        user_prompt = f"Génère le Quiz du jour ({target_date}). 3 questions d'association en français ET anglais. Chaque question doit avoir 4 paires à associer."

    return system_prompt, user_prompt


class DailyQuizGeneratorService:
    def __init__(self, db: Session):
        self.db = db

    def generate_quiz_of_the_day(self, target_date: date = None) -> DailyQuiz:
        """Génère via LLM et enregistre le quiz du jour selon le type déterminé."""
        import asyncio
        if not target_date:
            target_date = date.today()

        existing = (
            self.db.query(DailyQuiz)
            .filter(DailyQuiz.quiz_date == target_date)
            .first()
        )
        if existing:
            return existing

        quiz_type = get_quiz_type_of_the_day(target_date)
        system_prompt, prompt = get_prompt_for_type(quiz_type, target_date)

        try:
            from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
            from app.core.config import OPENROUTER_API_KEYS

            api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
            client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)

            # Run async LLM call in a separate thread with its own event loop
            import concurrent.futures
            def _run_llm():
                import asyncio as _asyncio
                loop = _asyncio.new_event_loop()
                _asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        client.generate(
                            messages=[{"role": "user", "content": prompt}],
                            system_instruction=system_prompt,
                            temperature=0.7,
                            max_tokens=3000,
                            response_format="json",
                        )
                    )
                finally:
                    loop.close()

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                response = executor.submit(_run_llm).result(timeout=180)

            # Debug: log raw response
            log.info(f"LLM response type: {type(response)}, keys: {response.keys() if isinstance(response, dict) else 'N/A'}")
            raw_text = response.get("text", "")
            log.info(f"LLM raw text (first 500 chars): {raw_text[:500]!r}")

            clean_json = raw_text.replace("```json", "").replace("```", "").strip()
            if not clean_json:
                error_code = response.get("error_code", "UNKNOWN")
                raise ValueError(f"Empty LLM response, error_code={error_code}")

            data = json.loads(clean_json)
            log.info(f"Parsed JSON keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")

            new_quiz = DailyQuiz(
                quiz_date=target_date,
                quiz_type=quiz_type,
                questions_json=data.get("questions", {}),
            )
            self.db.add(new_quiz)
            self.db.commit()
            self.db.refresh(new_quiz)
            return new_quiz
        except Exception as e:
            log.error(f"Erreur génération quiz du jour : {e}")
            raise e

    def get_today_quiz(self, user_id: str, user_langue: str = "fr") -> Optional[dict]:
        """Récupère le quiz du jour et vérifie si l'utilisateur y a déjà répondu."""
        today = date.today()
        quiz = self.db.query(DailyQuiz).filter(DailyQuiz.quiz_date == today).first()

        if not quiz:
            try:
                quiz = self.generate_quiz_of_the_day(today)
            except Exception:
                return None

        attempt = (
            self.db.query(DailyQuizAttempt)
            .filter(
                DailyQuizAttempt.user_id == user_id,
                DailyQuizAttempt.daily_quiz_id == quiz.id,
            )
            .first()
        )

        # Filtrer les questions selon la langue de l'utilisateur
        questions_data = quiz.questions_json or {}
        if isinstance(questions_data, list):
            questions = questions_data
        elif isinstance(questions_data, dict):
            questions = questions_data.get(user_langue, questions_data.get("fr", []))
        else:
            questions = []

        return {
            "id": quiz.id,
            "quiz_date": quiz.quiz_date,
            "quiz_type": quiz.quiz_type,
            "quiz_type_name": QUIZ_TYPE_NAMES.get(quiz.quiz_type, quiz.quiz_type),
            "questions": questions,
            "language": user_langue,
            "already_played": True if attempt else False,
            "score": attempt.score if attempt else None,
        }

    def submit_answers(
        self,
        user_id: str,
        quiz_id: int,
        user_answers: List[int] = None,
        text_answers: List[str] = None,
        ordering_answers: List[List[str]] = None,
        matching_answers: List[dict] = None,
        user_langue: str = "fr",
    ) -> dict:
        """Valide les réponses, enregistre l'essai et met à jour le leaderboard mensuel."""
        quiz = self.db.query(DailyQuiz).filter(DailyQuiz.id == quiz_id).first()
        if not quiz:
            raise ValueError("Quiz introuvable.")

        existing = (
            self.db.query(DailyQuizAttempt)
            .filter(
                DailyQuizAttempt.user_id == user_id,
                DailyQuizAttempt.daily_quiz_id == quiz_id,
            )
            .first()
        )
        if existing:
            raise ValueError("Vous avez déjà participé à ce quiz.")

        # Récupérer les questions dans la langue de l'utilisateur
        questions_data = quiz.questions_json or {}
        if isinstance(questions_data, list):
            questions = questions_data
        elif isinstance(questions_data, dict):
            questions = questions_data.get(user_langue, questions_data.get("fr", []))
        else:
            questions = []

        score = 0
        correct_data = []

        if quiz.quiz_type == "qcm":
            correct_indices = [q.get("correct_answer_index") for q in questions]
            for i, ans in enumerate(user_answers or []):
                if i < len(correct_indices) and ans == correct_indices[i]:
                    score += 1
            correct_data = correct_indices

        elif quiz.quiz_type == "true_false":
            correct_answers = [q.get("correct_answer") for q in questions]
            for i, ans in enumerate(user_answers or []):
                if i < len(correct_answers) and ans == correct_answers[i]:
                    score += 1
            correct_data = correct_answers

        elif quiz.quiz_type == "qro":
            for i, q in enumerate(questions):
                user_ans = (text_answers or [])[i] if text_answers else ""
                expected = q.get("expected_keyword", "").lower().strip()
                if expected in user_ans.lower() or user_ans.lower() in expected:
                    score += 1
            correct_data = [q.get("expected_keyword") for q in questions]

        elif quiz.quiz_type == "phrase_completion":
            for i, q in enumerate(questions):
                user_ans = (text_answers or [])[i] if text_answers else ""
                expected = q.get("missing_word", "").lower().strip()
                if expected in user_ans.lower() or user_ans.lower() in expected:
                    score += 1
            correct_data = [q.get("missing_word") for q in questions]

        elif quiz.quiz_type == "ordering":
            correct_orders = [q.get("correct_order", []) for q in questions]
            for i, ans in enumerate(ordering_answers or []):
                if i < len(correct_orders) and ans == correct_orders[i]:
                    score += 1
            correct_data = correct_orders

        elif quiz.quiz_type == "matching":
            correct_pairs = [q.get("pairs", []) for q in questions]
            for i, ans in enumerate(matching_answers or []):
                if i < len(correct_pairs) and ans == correct_pairs[i]:
                    score += 1
            correct_data = correct_pairs

        attempt = DailyQuizAttempt(
            user_id=user_id, daily_quiz_id=quiz_id, score=score
        )
        self.db.add(attempt)

        month_str = datetime.now().strftime("%Y-%m")
        board = (
            self.db.query(MonthlyLeaderboard)
            .filter(
                MonthlyLeaderboard.user_id == user_id,
                MonthlyLeaderboard.month_year == month_str,
            )
            .first()
        )

        if not board:
            board = MonthlyLeaderboard(
                user_id=user_id, month_year=month_str, total_score=score
            )
            self.db.add(board)
        else:
            board.total_score += score

        self.db.commit()

        return {
            "score": score,
            "total": len(questions),
            "correct_answers": correct_data,
            "month_total_points": board.total_score,
        }

    def get_leaderboard(self, user_id: str, limit: int = 50) -> dict:
        """Récupère le Top 50 du mois en cours."""
        month_str = datetime.now().strftime("%Y-%m")

        results = (
            self.db.query(
                MonthlyLeaderboard.user_id,
                User.prenom,
                MonthlyLeaderboard.total_score,
            )
            .join(User, MonthlyLeaderboard.user_id == User.id)
            .filter(MonthlyLeaderboard.month_year == month_str)
            .order_by(desc(MonthlyLeaderboard.total_score))
            .limit(limit)
            .all()
        )

        top_players = []
        user_rank_entry = None

        for rank, res in enumerate(results, start=1):
            entry = {
                "user_id": str(res[0]),
                "prenom": res[1],
                "total_score": res[2],
                "rank": rank,
            }
            top_players.append(entry)
            if str(res[0]) == user_id:
                user_rank_entry = entry

        if not user_rank_entry:
            user_board = (
                self.db.query(MonthlyLeaderboard)
                .filter(
                    MonthlyLeaderboard.user_id == user_id,
                    MonthlyLeaderboard.month_year == month_str,
                )
                .first()
            )
            if user_board:
                rank_pos = (
                    self.db.query(MonthlyLeaderboard)
                    .filter(
                        MonthlyLeaderboard.month_year == month_str,
                        MonthlyLeaderboard.total_score > user_board.total_score,
                    )
                    .count()
                    + 1
                )
                user_res = self.db.query(User).filter(User.id == user_id).first()
                user_rank_entry = {
                    "user_id": user_id,
                    "prenom": user_res.prenom if user_res else "Moi",
                    "total_score": user_board.total_score,
                    "rank": rank_pos,
                }

        return {
            "month": month_str,
            "top_players": top_players,
            "user_rank": user_rank_entry,
        }
