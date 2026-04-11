"""
services/churn_detector_service.py
==================================
Service pour detecter les utilisateurs a risque de desabonnement.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.modules.users.models import User, AuditLog
from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)

# Seuil d'inactivite en jours pour declencher une alerte
INACTIVITY_THRESHOLD_DAYS = 7


class ChurnDetectorService(BaseService):
    """Service pour identifier les utilisateurs inactifs avec abonnement actif."""

    def detecter_et_alerter(self) -> List[Dict[str, Any]]:
        """
        Trouve les utilisateurs inactifs depuis plus de 7 jours avec un
        abonnement actif (plan != freemium), consigne un warning dans l'audit log,
        et retourne la liste des utilisateurs concernes.

        Returns:
            Liste de dictionnaires avec les informations de chaque utilisateur a risque.
        """
        seuil = datetime.utcnow() - timedelta(days=INACTIVITY_THRESHOLD_DAYS)

        # Plans consideres comme "actifs" (payants)
        plans_actifs = ["access", "premium", "pro", "unlimited", "school"]

        users_a_risque = (
            self.db.query(User)
            .filter(
                User.plan_effectif.in_(plans_actifs),
                User.is_active == True,  # noqa: E712
                User.derniere_activite_at < seuil,
            )
            .all()
        )

        if not users_a_risque:
            logger.info("No churn risk users detected.")
            return []

        resultats = []
        for user in users_a_risque:
            jours_inactif = 0
            if user.derniere_activite_at:
                jours_inactif = (datetime.utcnow() - user.derniere_activite_at).days

            info = {
                "user_id": str(user.id),
                "email": user.email,
                "prenom": user.prenom,
                "plan_effectif": user.plan_effectif,
                "derniere_activite_at": (
                    user.derniere_activite_at.isoformat() if user.derniere_activite_at else None
                ),
                "jours_inactif": jours_inactif,
                "streak_jours": user.streak_jours,
                "score_global": user.score_global,
            }
            resultats.append(info)

            # Consigner dans l'audit log
            audit_entry = AuditLog(
                user_id=user.id,
                action="churn_risk_detected",
                resource="users",
                resource_id=str(user.id),
                details={
                    "plan": user.plan_effectif,
                    "days_inactive": jours_inactif,
                    "score_global": user.score_global,
                },
                severity="warning",
            )
            self.db.add(audit_entry)

            logger.warning(
                f"Churn risk: {user.email} (plan={user.plan_effectif}, "
                f"inactive {jours_inactif} days)"
            )

        self.db.commit()

        logger.info(f"Churn detection complete: {len(resultats)} users at risk.")
        return resultats
