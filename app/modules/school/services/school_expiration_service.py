"""
services/school_expiration_service.py
=====================================
Service de gestion des expirations d'ecoles : alertes, expiration, reactivation.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.school.models.school import School
from app.modules.school.models.school_member import SchoolMember
from app.modules.school.services.base import SchoolBaseService

logger = logging.getLogger(__name__)


class SchoolExpirationService(SchoolBaseService):
    """Service de gestion des expirations d'ecoles."""

    def verifier_expirations(self) -> int:
        """Verifie les ecoles qui expirent dans 7, 3, 1 jours et envoie des alertes.

        Retourne le nombre d'ecoles alertees.
        """
        aujourd_hui = datetime.utcnow()
        alertes_envoyees = 0

        for delta_days in [7, 3, 1]:
            date_cible = aujourd_hui + timedelta(days=delta_days)
            flag_field = f"alerte_expiration_j{delta_days}_envoyee"

            ecoles = (
                self.db.query(School)
                .filter(
                    School.is_active == True,  # noqa: E712
                    School.date_expiration >= date_cible,
                    School.date_expiration < date_cible + timedelta(days=1),
                    getattr(School, flag_field) == False,  # noqa: E712
                )
                .all()
            )

            for ecole in ecoles:
                # Marquer l'alerte comme envoyee
                setattr(ecole, flag_field, True)
                alertes_envoyees += 1

                # Envoyer une notification
                self._send_expiration_alert(ecole, delta_days)

        if alertes_envoyees > 0:
            self.db.commit()
            logger.info(
                "Alertes d'expiration envoyees pour %d ecoles", alertes_envoyees
            )

        return alertes_envoyees

    def expirer_ecoles(self) -> int:
        """Desactive les ecoles dont la date d'expiration est passee.

        Retourne le nombre d'ecoles expirees.
        """
        aujourd_hui = datetime.utcnow()

        ecoles_expirees = (
            self.db.query(School)
            .filter(
                School.is_active == True,  # noqa: E712
                School.date_expiration < aujourd_hui,
            )
            .all()
        )

        nb_expire = 0
        for ecole in ecoles_expirees:
            # Desactiver l'ecole
            ecole.is_active = False
            nb_expire += 1

            # Remettre tous les membres en freemium
            (
                self.db.query(User)
                .join(
                    SchoolMember, SchoolMember.user_id == User.id
                )
                .filter(
                    SchoolMember.school_id == ecole.id,
                    SchoolMember.is_active == True,  # noqa: E712
                )
                .update(
                    {
                        User.plan_effectif: "freemium",
                        User.school_id: None,
                    },
                    synchronize_session="fetch",
                )
            )

            logger.info("Ecole expiree: %s (%s)", ecole.nom, ecole.id)

        if nb_expire > 0:
            self.db.commit()
            logger.info("%d ecoles expirees", nb_expire)

        return nb_expire

    async def reactiver_ecole(
        self,
        school_id: str,
        nouvelle_expiration: Optional[datetime] = None,
    ) -> dict:
        """Reactive une ecole et prolonge sa date d'expiration.

        Si aucune date n'est fournie, prolonge de 30 jours.
        """
        ecole = self.db.query(School).filter(School.id == school_id).first()
        if ecole is None:
            raise ValueError("Ecole introuvable")

        # Reactiver l'ecole
        ecole.is_active = True

        # Prolonger l'expiration
        if nouvelle_expiration is None:
            nouvelle_expiration = datetime.utcnow() + timedelta(days=30)
        ecole.date_expiration = nouvelle_expiration

        # Reset les alertes d'expiration
        ecole.alerte_expiration_j7_envoyee = False
        ecole.alerte_expiration_j3_envoyee = False
        ecole.alerte_expiration_j1_envoyee = False

        # Remettre tous les membres en plan school
        (
            self.db.query(User)
            .join(SchoolMember, SchoolMember.user_id == User.id)
            .filter(SchoolMember.school_id == school_id)
            .update(
                {User.plan_effectif: "school"},
                synchronize_session="fetch",
            )
        )

        self.db.commit()

        logger.info(
            "Ecole reactivee: %s (%s), expiration: %s",
            ecole.nom,
            ecole.id,
            nouvelle_expiration,
        )

        return {
            "message": f"Ecole '{ecole.nom}' reactivee",
            "school_id": school_id,
            "date_expiration": nouvelle_expiration.isoformat(),
            "is_active": True,
        }

    # ─── Helpers internes ──────────────────────────────────────────────

    def _send_expiration_alert(self, ecole: School, jours_restants: int):
        """Envoie une alerte d'expiration pour une ecole."""
        # Tenter d'importer le NotificationService
        try:
            from app.modules.notifications.services.notification_service import (
                NotificationService,
            )

            notif_service = NotificationService(self.db, self.redis)
            admin_id = ecole.admin_id

            notif_service.send_to_user(
                user_id=admin_id,
                title=f"Ecole '{ecole.nom}' — Expiration imminente",
                body=f"Il ne reste que {jours_restants} jour(s) avant l'expiration de votre ecole. "
                f"Pensez a renouveler votre abonnement.",
                type_notif="school_expiration",
                data={
                    "school_id": ecole.id,
                    "jours_restants": jours_restants,
                    "date_expiration": ecole.date_expiration.isoformat()
                    if ecole.date_expiration
                    else None,
                },
            )
        except ImportError:
            logger.warning(
                "NotificationService indisponible, alerte non envoyee pour l'ecole %s",
                ecole.id,
            )


# Import necessaire pour la mise a jour des utilisateurs dans expirer_ecoles
from app.modules.users.models.user import User  # noqa: E402
