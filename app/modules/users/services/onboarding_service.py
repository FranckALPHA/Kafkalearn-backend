"""
services/onboarding_service.py
==============================
Service pour gerer le processus d'onboarding des nouveaux utilisateurs.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.users.models import User, UserLearningProfile
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)


class OnboardingService(BaseService):
    """Service pour completer l'onboarding d'un utilisateur."""

    def completer_onboarding(
        self,
        user_id: str,
        classe: str,
        serie: str,
        langue: str = "fr",
        matiere_forte: Optional[str] = None,
        matiere_faible: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Complete l'onboarding d'un utilisateur en definissant ses informations
        scolaires et en marquant onboarding_completed=True.

        Args:
            user_id: UUID de l'utilisateur.
            classe: Classe de l'eleve (ex: "Terminale", "Premiere").
            serie: Serie (ex: "C", "D", "A", "TI").
            langue: Langue principale ('fr' ou 'en').
            matiere_forte: Matiere forte de l'eleve.
            matiere_faible: Matiere faible de l'eleve.

        Returns:
            Dictionnaire avec les informations de l'utilisateur mis a jour.

        Raises:
            ValueError: Si l'utilisateur n'existe pas.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("USER_NOT_FOUND")

        # Mettre a jour les champs d'onboarding
        user.classe = classe
        user.serie = serie
        user.langue = langue
        user.matiere_forte = matiere_forte
        user.matiere_faible = matiere_faible
        user.onboarding_completed = True

        # Verifier/creer le profil d'apprentissage s'il manque
        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )
        if not profile:
            profile = UserLearningProfile(
                user_id=user.id,
                interets=[matiere_forte] if matiere_forte else [],
            )
            self.db.add(profile)
            logger.info(f"Created learning profile for user {user_id}")
        else:
            # Mettre a jour les interets si matiere_forte est fournie
            if matiere_forte:
                interets = profile.interets or []
                if matiere_forte not in interets:
                    interets.append(matiere_forte)
                    profile.interets = interets

        # Initialiser le niveau estime a partir des matieres
        if matiere_forte and matiere_faible:
            user.niveau_estime = "moyen"  # Sera affine par les quiz
        elif matiere_forte:
            user.niveau_estime = "fort"
        elif matiere_faible:
            user.niveau_estime = "faible"

        self.db.commit()
        self._invalidate_profile_cache(str(user_id))

        return {
            "user_id": str(user.id),
            "email": user.email,
            "prenom": user.prenom,
            "classe": user.classe,
            "serie": user.serie,
            "langue": user.langue,
            "matiere_forte": user.matiere_forte,
            "matiere_faible": user.matiere_faible,
            "onboarding_completed": user.onboarding_completed,
            "niveau_estime": user.niveau_estime,
        }
