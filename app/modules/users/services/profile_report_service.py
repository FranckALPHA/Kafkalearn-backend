"""
services/profile_report_service.py
==================================
Service pour la generation asynchrone de rapports de profil utilisateur.
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from redis import Redis

from app.modules.users.services.base import BaseService

logger = logging.getLogger(__name__)


class ProfileReportService(BaseService):
    """Service pour creer et suivre les rapports de profil asynchrones."""

    def generer_rapport_async(self, user_id: str, declencheur: str = "manual") -> str:
        """
        Cree une entree de rapport et retourne un report_id pour un
        traitement asynchrone ulterieur.

        Le rapport peut etre declenche par : 'manual', 'scheduled', 'churn_alert'.

        Args:
            user_id: UUID de l'utilisateur.
            declencheur: Origine de la demande de rapport.

        Returns:
            UUID du rapport cree (report_id).
        """
        report_id = str(uuid.uuid4())

        # Stocker le statut du rapport dans Redis pour suivi
        report_data = {
            "report_id": report_id,
            "user_id": str(user_id),
            "status": "pending",
            "declencheur": declencheur,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "result": None,
        }

        cache_key = f"report:status:{report_id}"
        try:
            import json
            self.redis.setex(
                cache_key,
                86400,  # 24h TTL
                json.dumps(report_data, default=str),
            )
        except Exception as e:
            logger.error(f"Failed to store report status in Redis: {e}")

        logger.info(
            f"Report created: {report_id} for user {user_id} "
            f"(trigger: {declencheur})"
        )

        return report_id

    def get_rapport_status(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne le statut actuel d'un rapport.

        Args:
            report_id: UUID du rapport.

        Returns:
            Dictionnaire avec le statut du rapport, ou None si inexistant.
        """
        cache_key = f"report:status:{report_id}"
        try:
            import json
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"Failed to retrieve report status from Redis: {e}")

        return None

    def update_rapport_status(
        self,
        report_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Met a jour le statut d'un rapport (utile pour le worker asynchrone).

        Args:
            report_id: UUID du rapport.
            status: Nouveau statut ('pending', 'processing', 'completed', 'failed').
            result: Resultat du rapport (si completed).

        Returns:
            True si la mise a jour a reussi.
        """
        cache_key = f"report:status:{report_id}"
        try:
            import json
            cached = self.redis.get(cache_key)
            if not cached:
                logger.warning(f"Report {report_id} not found in cache.")
                return False

            report_data = json.loads(cached)
            report_data["status"] = status
            report_data["result"] = result
            if status in ("completed", "failed"):
                report_data["completed_at"] = datetime.utcnow().isoformat()

            self.redis.setex(
                cache_key,
                86400,
                json.dumps(report_data, default=str),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update report status in Redis: {e}")
            return False
