import json
import logging
import hashlib
from datetime import date, datetime
from sqlalchemy.orm import Session
from redis import Redis

from app.modules.daily_quiz.services.base import DailyQuizBaseService
from app.modules.daily_quiz.models import DailyQuiz
from app.modules.daily_quiz.utils import ThemeRotator, QuestionValidator

logger = logging.getLogger(__name__)


class DailyQuizGeneratorService(DailyQuizBaseService):
    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)
        self.theme_rotator = ThemeRotator()

    async def generer_quiz_du_jour(self, date_cible: date, force: bool = False) -> dict:
        """Generate or retrieve the daily quiz for a given date."""
        existing = (
            self.db.query(DailyQuiz)
            .filter(DailyQuiz.quiz_date == date_cible)
            .first()
        )

        if existing and not force:
            return existing.serialize_public()

        # Determine theme and difficulty
        theme = self.theme_rotator.get_theme_for_date(date_cible)

        try:
            from app.modules.daily_quiz.services.quiz_adaptivity_service import QuizAdaptivityService
            adaptivity = QuizAdaptivityService(self.db, self.redis)
            difficulte = await adaptivity.calculer_difficulte_pour_demain()
        except Exception:
            logger.warning("Could not determine adaptive difficulty, defaulting to 'moyen'")
            difficulte = "moyen"

        # Try LLM generation
        try:
            questions_fr = await self._generate_questions_llm(theme, difficulte, "fr")
            questions_en = await self._generate_questions_llm(theme, difficulte, "en")
        except Exception as exc:
            logger.error("LLM generation failed: %s", exc)
            return self._fallback_statique(date_cible)

        if not questions_fr or not questions_en:
            return self._fallback_statique(date_cible)

        questions_json = {"fr": questions_fr, "en": questions_en}

        quiz = DailyQuiz(
            quiz_date=date_cible,
            quiz_type="qcm",
            theme=theme,
            difficulte=difficulte,
            nb_questions=len(questions_fr),
            questions_json=questions_json,
            source="llm",
        )
        self.db.add(quiz)
        self.db.commit()
        self.db.refresh(quiz)

        return quiz.serialize_public()

    async def _generate_questions_llm(self, theme: str, difficulte: str, langue: str) -> list:
        """Generate quiz questions via LLM for the given theme, difficulty, and language."""
        try:
            from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
            from app.core.config import (
                OPENROUTER_API_KEYS,
            )
        except ImportError:
            logger.error("Cannot import LLM client or config")
            return []

        api_keys = {
            "openrouter_api_keys": OPENROUTER_API_KEYS,
        }

        client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)

        prompt = (
            f"Genere 5 questions QCM sur le theme '{theme}' avec une difficulte '{difficulte}' "
            f"en langue '{langue}'. Chaque question doit avoir un enonce, 4 options (A, B, C, D), "
            f"une bonne_reponse (qui doit etre l'une des options), et une explication. "
            f"Retourne UNIQUEMENT un tableau JSON valide sans texte supplementaire."
        )

        try:
            result = await client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                response_format="json",
            )
        finally:
            await client.close()

        if result.get("error_code"):
            logger.error("LLM generation returned error: %s", result.get("error_code"))
            return []

        try:
            text = result.get("text", "")
            questions = json.loads(text)
            if not isinstance(questions, list):
                logger.error("LLM response is not a list")
                return []

            validated = []
            for q in questions:
                if QuestionValidator.validate(q, "qcm"):
                    validated.append(q)

            return validated
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response as JSON")
            return []

    def _fallback_statique(self, date_cible: date) -> dict:
        """Return a static quiz based on a date hash when LLM is unavailable."""
        date_str = str(date_cible)
        hash_val = int(hashlib.md5(date_str.encode()).hexdigest(), 16)

        static_questions_fr = [
            {
                "enonce": "Quelle est la capitale du Cameroun?",
                "options": ["Douala", "Yaounde", "Bafoussam", "Garoua"],
                "bonne_reponse": "Yaounde",
                "explication": "Yaounde est la capitale politique du Cameroun depuis l'independance.",
            },
            {
                "enonce": "En quelle annee le Cameroun a-t-il obtenu son independance?",
                "options": ["1955", "1960", "1961", "1972"],
                "bonne_reponse": "1960",
                "explication": "Le Cameroun a obtenu son independance le 1er janvier 1960.",
            },
            {
                "enonce": "Quel est le plus long fleuve du Cameroun?",
                "options": ["Sanaga", "Benoue", "Wouri", "Nyong"],
                "bonne_reponse": "Sanaga",
                "explication": "La Sanaga est le plus long fleuve du Cameroun avec environ 918 km.",
            },
            {
                "enonce": "Combien de regions compte le Cameroun?",
                "options": ["8", "10", "12", "14"],
                "bonne_reponse": "10",
                "explication": "Le Cameroun est divise en 10 regions depuis 2008.",
            },
            {
                "enonce": "Quelle est la monnaie officielle du Cameroun?",
                "options": ["Franc CFA", "Naira", "Shilling", "Kwacha"],
                "bonne_reponse": "Franc CFA",
                "explication": "Le Cameroun utilise le Franc CFA (XAF) comme monnaie officielle.",
            },
        ]

        # Shuffle based on date hash
        indices = [(hash_val + i * 7) % len(static_questions_fr) for i in range(5)]
        selected = [static_questions_fr[i % len(static_questions_fr)] for i in indices]

        quiz_data = {
            "quiz_date": date_cible,
            "quiz_type": "qcm",
            "theme": self.theme_rotator.get_theme_for_date(date_cible),
            "difficulte": "moyen",
            "nb_questions": 5,
            "questions_json": {"fr": selected, "en": selected},
            "source": "static",
        }

        quiz = DailyQuiz(**quiz_data)
        self.db.add(quiz)
        self.db.commit()
        self.db.refresh(quiz)

        return quiz.serialize_public()
