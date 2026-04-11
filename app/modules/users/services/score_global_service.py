"""
services/score_global_service.py
================================
Service pour le calcul du score global de l'utilisateur.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.modules.users.models import User, UserLearningProfile, UserActivity
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)


class ScoreGlobalService(BaseService):
    """Service pour recalculer le score global d'un utilisateur."""

    def recalculer(self, user_id: str) -> Dict[str, Any]:
        """
        Calcule le score global a partir de plusieurs facteurs :
        - Taux de reussite aux quiz (40%)
        - Heures d'etude (20%)
        - Streak actuel (20%)
        - Completude du profil (20%)

        Met a jour user.score_global et progression_hebdo.

        Args:
            user_id: UUID de l'utilisateur.

        Returns:
            Dictionnaire avec le nouveau score et les details du calcul.

        Raises:
            ValueError: Si l'utilisateur n'existe pas.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        # ─── 1. Taux de reussite aux quiz (40%) ────────────────────
        total_quiz = (user.nb_quiz_reussis or 0) + (user.nb_quiz_echoues or 0)
        if total_quiz > 0:
            quiz_score = ((user.nb_quiz_reussis or 0) / total_quiz) * 100
        else:
            quiz_score = 0.0

        # ─── 2. Heures d'etude (20%) ──────────────────────────────
        # Plafonne a 50h = score max
        heures = user.total_heures_etude or 0.0
        study_score = min((heures / 50.0) * 100, 100)

        # ─── 3. Streak actuel (20%) ───────────────────────────────
        # Plafonne a 30 jours = score max
        streak = user.streak_jours or 0
        streak_score = min((streak / 30.0) * 100, 100)

        # ─── 4. Completude du profil (20%) ────────────────────────
        profile_completeness = self._calculer_completude_profil(user)

        # ─── Score final pondere ──────────────────────────────────
        score_global = (
            quiz_score * 0.4
            + study_score * 0.2
            + streak_score * 0.2
            + profile_completeness * 0.2
        )
        score_global = round(min(max(score_global, 0), 100), 2)

        # ─── Progression hebdomadaire ─────────────────────────────
        ancien_score = user.score_global or 0.0
        progression = score_global - ancien_score
        user.score_global = score_global
        user.progression_hebdo = round(progression, 2)

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        return {
            "score_global": score_global,
            "progression_hebdo": user.progression_hebdo,
            "details": {
                "quiz_score": round(quiz_score, 2),
                "study_score": round(study_score, 2),
                "streak_score": round(streak_score, 2),
                "profile_completeness": round(profile_completeness, 2),
                "total_quiz": total_quiz,
                "heures_etude": heures,
                "streak_jours": streak,
            },
        }

    def _calculer_completude_profil(self, user: User) -> float:
        """
        Calcule le pourcentage de completude du profil utilisateur.

        Args:
            user: Instance de l'utilisateur.

        Returns:
            Pourcentage de completude (0-100).
        """
        champs = [
            user.prenom,
            user.nom,
            user.phone,
            user.photo_url,
            user.classe,
            user.serie,
            user.region,
            user.etablissement,
            user.langue,
        ]
        remplis = sum(1 for c in champs if c)
        return (remplis / len(champs)) * 100
