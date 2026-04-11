"""
services/streak_service.py
==========================
Service pour la gestion des streaks (serie de jours consecutifs) et de l'activite.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.users.models import User, UserActivity
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)


class StreakService(BaseService):
    """Service pour calculer les streaks et enregistrer l'activite utilisateur."""

    def calculer_streak(self, user_id: str) -> Dict[str, Any]:
        """
        Calcule le streak actuel (jours consecutifs depuis la derniere activite)
        et met a jour user.streak_jours et streak_max.

        Args:
            user_id: UUID de l'utilisateur.

        Returns:
            Dictionnaire avec streak_jours, streak_max, et derniere_activite_at.

        Raises:
            ValueError: Si l'utilisateur n'existe pas.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        now = datetime.utcnow()
        last_activity = user.derniere_activite_at

        if not last_activity:
            # Aucune activite precedente, streak = 0
            user.streak_jours = 0
            self.db.commit()
            return {
                "streak_jours": 0,
                "streak_max": user.streak_max or 0,
                "derniere_activite_at": None,
            }

        # Calculer la difference en jours
        diff_days = (now.date() - last_activity.date()).days

        if diff_days == 0:
            # Activite aujourd'hui, streak conserve
            pass
        elif diff_days == 1:
            # Activite hier, on incrementera quand une activite sera enregistree
            pass
        elif diff_days > 1:
            # Plus d'un jour sans activite, streak remis a 0
            user.streak_jours = 0
            self.db.commit()
            return {
                "streak_jours": 0,
                "streak_max": user.streak_max or 0,
                "derniere_activite_at": last_activity.isoformat(),
            }

        return {
            "streak_jours": user.streak_jours or 0,
            "streak_max": user.streak_max or 0,
            "derniere_activite_at": last_activity.isoformat() if last_activity else None,
        }

    def enregistrer_activite(
        self,
        user_id: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Enregistre une activite utilisateur, met a jour les timestamps
        et calcule le streak.

        Args:
            user_id: UUID de l'utilisateur.
            action: Type d'action (login, quiz, search, etc.).
            details: Metadata contextuelle.
            ip: Adresse IP de la requete.
            user_agent: User-Agent du navigateur.

        Returns:
            Dictionnaire avec les informations de streak mises a jour.

        Raises:
            ValueError: Si l'utilisateur n'existe pas.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        now = datetime.utcnow()

        # Creer l'entree d'activite
        activity = UserActivity(
            user_id=user.id,
            action=action,
            details=details or {},
            ip_address=ip,
            user_agent=user_agent,
        )
        self.db.add(activity)

        # Mettre a jour les timestamps
        user.derniere_activite_at = now

        if action == "login":
            user.derniere_connexion_at = now

        # Calculer le streak
        last_activity = user.derniere_activite_at
        if last_activity:
            diff_days = (now.date() - last_activity.date()).days if last_activity else 999
        else:
            diff_days = 999

        if diff_days <= 1:
            # Activite consecutive (aujourd'hui ou hier)
            current_streak = user.streak_jours or 0
            if diff_days == 1 or not last_activity:
                # Nouveau jour consecutif
                current_streak += 1
            user.streak_jours = current_streak
            user.streak_max = max(user.streak_max or 0, current_streak)
        else:
            # Streak rompu, recommencer a 1
            user.streak_jours = 1
            user.streak_max = max(user.streak_max or 0, 1)

        # Incrementer le compteur de sessions
        user.total_sessions_etude = (user.total_sessions_etude or 0) + 1

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        return {
            "streak_jours": user.streak_jours,
            "streak_max": user.streak_max,
            "derniere_activite_at": now.isoformat(),
            "total_sessions": user.total_sessions_etude,
        }
