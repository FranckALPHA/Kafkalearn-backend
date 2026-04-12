"""
services/school_quota_service.py
=================================
Service de gestion des quotas IA journaliers par ecole.
"""
import logging
from datetime import datetime, timedelta, date

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.school.models.school import School
from app.modules.school.models.school_ai_usage import SchoolAIUsage
from app.modules.school.services.base import SchoolBaseService
from app.modules.school.utils.pricing_calculator import PricingCalculator

logger = logging.getLogger(__name__)


class SchoolQuotaService(SchoolBaseService):
    """Service de gestion des quotas IA journaliers."""

    QUOTA_PAR_SIEGE = 25

    def _build_quota_key(self, school_id: str, dt: date = None) -> str:
        """Construit la cle Redis pour le quota du jour."""
        if dt is None:
            dt = datetime.utcnow().date()
        return f"school:quota:{school_id}:{dt.isoformat()}"

    async def verifier_et_consommer_quota(
        self, school_id: str, nb_eleves_max: int
    ) -> bool:
        """Verifie et consomme une unite de quota de maniere atomique.

        Retourne True si le quota est disponible, False sinon.
        """
        pricing = PricingCalculator()
        quota_total = pricing.calculer_quota_ia_journalier(nb_eleves_max)
        key = self._build_quota_key(school_id)

        try:
            # Pipeline atomique GET + INCR
            pipe = self.redis.pipeline(True)
            pipe.get(key)
            pipe.incr(key)
            pipe.expire(key, 86400 * 2)  # 2 jours d'expiration
            results = pipe.execute()

            current = int(results[0]) if results[0] is not None else 0
            new_val = int(results[1])

            if new_val > quota_total:
                logger.warning(
                    "Quota depasse pour l'ecole %s: %d/%d",
                    school_id,
                    new_val,
                    quota_total,
                )
                # On decremente pour annuler
                self.redis.decr(key)
                return False

            return True

        except Exception as e:
            logger.error(
                "Erreur Redis lors de la verification du quota: %s", e
            )
            # En cas d'erreur Redis, on autorise par defaut (fail-open)
            return True

    async def obtenir_stats_jour(self, school_id: str) -> dict:
        """Retourne les statistiques de quota du jour."""
        key = self._build_quota_key(school_id)
        today = datetime.utcnow().date()

        try:
            consomme = int(self.redis.get(key) or 0)
        except Exception:
            consomme = 0

        # Recupere le quota total depuis l'ecole
        school = self.db.query(School).filter(School.id == school_id).first()
        if school is None:
            raise ValueError("Ecole introuvable")

        pricing = PricingCalculator()
        quota_total = pricing.calculer_quota_ia_journalier(school.nb_eleves_max)
        quota_restant = max(0, quota_total - consomme)
        taux_utilisation = (
            round((consomme / quota_total) * 100, 2) if quota_total > 0 else 0.0
        )

        return {
            "quota_total_aujourd_hui": quota_total,
            "quota_consomme_aujourd_hui": consomme,
            "quota_restant": quota_restant,
            "taux_utilisation": taux_utilisation,
        }

    async def consolider_quota_jour(self, school_id: str):
        """Consolide le quota d'hier dans la table SchoolAIUsage."""
        hier = datetime.utcnow().date() - timedelta(days=1)
        redis_key = self._build_quota_key(school_id, hier)

        try:
            quota_consomme = int(self.redis.get(redis_key) or 0)
        except Exception:
            logger.warning(
                "Impossible de lire le quota Redis pour %s le %s",
                school_id,
                hier,
            )
            return

        # Recupere le quota total de l'ecole
        school = self.db.query(School).filter(School.id == school_id).first()
        if school is None:
            logger.warning("Ecole %s introuvable pour consolidation", school_id)
            return

        pricing = PricingCalculator()
        quota_total = pricing.calculer_quota_ia_journalier(school.nb_eleves_max)

        # Upsert dans SchoolAIUsage
        usage = (
            self.db.query(SchoolAIUsage)
            .filter(SchoolAIUsage.school_id == school_id, SchoolAIUsage.date == hier)
            .first()
        )

        if usage is None:
            usage = SchoolAIUsage(
                school_id=school_id,
                date=hier,
                quota_total=quota_total,
                quota_consomme=quota_consomme,
                nb_utilisateurs_actifs=0,
            )
            self.db.add(usage)
        else:
            usage.quota_total = quota_total
            usage.quota_consomme = quota_consomme

        self.db.commit()
        logger.info(
            "Quota consolide pour l'ecole %s le %s: %d/%d",
            school_id,
            hier,
            quota_consomme,
            quota_total,
        )
