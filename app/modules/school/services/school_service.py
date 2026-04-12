"""
services/school_service.py
==========================
Service principal pour la gestion des ecoles : creation, rejoindre, dashboard, suppression.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.school.models.school import School
from app.modules.school.models.school_member import SchoolMember
from app.modules.school.services.base import SchoolBaseService
from app.modules.school.utils.code_generator import CodeGenerator
from app.modules.school.utils.pricing_calculator import PricingCalculator
from app.modules.school.utils.constants import SCHOOL_MIN_SEATS
from app.modules.users.models.user import User

logger = logging.getLogger(__name__)


class SchoolService(SchoolBaseService):
    """Service de gestion des ecoles."""

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)
        self.pricing = PricingCalculator()

    # ─── Creation d'une ecole ──────────────────────────────────────────

    async def creer_ecole(
        self,
        admin_user: User,
        nom: str,
        ville: str,
        pays: str = "CM",
        region: Optional[str] = None,
        nb_sieges: int = 10,
        description: Optional[str] = None,
    ) -> dict:
        """Cree une nouvelle ecole et inscrit l'utilisateur comme admin."""
        # Validation du nombre de sieges
        if nb_sieges < SCHOOL_MIN_SEATS:
            raise ValueError(
                f"Minimum {SCHOOL_MIN_SEATS} sieges requis, {nb_sieges} fourni"
            )

        # Verifier que l'utilisateur n'est pas deja dans une ecole
        if admin_user.school_id is not None:
            raise ValueError("L'utilisateur appartient deja a une ecole")

        # Generer les codes
        school_id = CodeGenerator.generate_school_id()
        code_invitation = CodeGenerator.generate_invitation_code()

        # Calculer la date d'expiration (30 jours d'essai)
        date_creation = datetime.utcnow()
        date_expiration = date_creation + timedelta(days=30)

        # Creer l'ecole
        school = School(
            id=school_id,
            nom=nom,
            ville=ville,
            pays=pays,
            region=region,
            admin_id=admin_user.id,
            nb_eleves_max=nb_sieges,
            code_invitation=code_invitation,
            date_creation=date_creation,
            date_expiration=date_expiration,
            is_active=True,
            description=description,
        )
        self.db.add(school)

        # Creer le membre admin
        admin_member = SchoolMember(
            school_id=school_id,
            user_id=admin_user.id,
            role_ecole="admin",
            invited_via="admin_direct",
        )
        self.db.add(admin_member)

        # Mettre a jour l'utilisateur
        admin_user.plan_effectif = "school"
        admin_user.school_id = school_id

        self.db.commit()
        self.db.refresh(school)

        # Calculer les informations de pricing
        prix_par_siege = self.pricing.calculer_prix_par_siege(nb_sieges)
        prix_mensuel = self.pricing.calculer_prix_mensuel(nb_sieges)
        quota_journalier = self.pricing.calculer_quota_ia_journalier(nb_sieges)

        return {
            "school": school.serialize_dashboard(is_admin=True),
            "pricing": {
                "prix_par_siege": prix_par_siege,
                "prix_mensuel": prix_mensuel,
                "quota_ia_journalier": quota_journalier,
                "tranche": self.pricing.calculer_tranche(nb_sieges),
            },
            "message": f"Ecole '{nom}' creee avec succes",
        }

    # ─── Rejoindre une ecole par code ──────────────────────────────────

    async def rejoindre_par_code(self, user: User, code: str) -> dict:
        """Permet a un utilisateur de rejoindre une ecole via un code d'invitation."""
        # Valider le format du code
        if not CodeGenerator.validate_invitation_code(code):
            raise ValueError("Format de code d'invitation invalide")

        # Chercher l'ecole par code
        school = (
            self.db.query(School)
            .filter(School.code_invitation == code)
            .first()
        )
        if school is None:
            raise ValueError("Code d'invitation invalide")

        # Verifier que l'ecole est active
        if not school.is_active:
            raise ValueError("Cette ecole n'est plus active")

        # Verifier que l'ecole n'est pas expiree
        if school.date_expiration and school.date_expiration < datetime.utcnow():
            raise ValueError("Cette ecole a expire")

        # Verifier que l'utilisateur n'est pas deja dans une ecole
        if user.school_id is not None:
            raise ValueError("Vous appartenez deja a une ecole")

        # Verifier que l'ecole n'est pas pleine
        if school.nb_eleves_actifs >= school.nb_eleves_max:
            raise ValueError("Cette ecole a atteint sa capacite maximale")

        # Creer le membre
        member = SchoolMember(
            school_id=school.id,
            user_id=user.id,
            role_ecole="eleve",
            invited_via="code",
        )
        self.db.add(member)

        # Mettre a jour l'utilisateur
        user.plan_effectif = "school"
        user.school_id = school.id

        # Mettre a jour le nombre d'eleves actifs
        school.nb_eleves_actifs += 1

        self.db.commit()

        return {
            "message": f"Bienvenue a l'ecole '{school.nom}'",
            "school": school.serialize_dashboard(),
            "member": member.serialize_profile(mask_email=False),
        }

    # ─── Dashboard ─────────────────────────────────────────────────────

    async def recuperer_dashboard(
        self, school_id: str, user_id: str, is_admin: bool
    ) -> dict:
        """Recupere les donnees du dashboard d'une ecole."""
        from app.modules.school.services.school_engagement_service import (
            SchoolEngagementService,
        )
        from app.modules.school.services.school_quota_service import SchoolQuotaService

        # Recuperer l'ecole
        school = self.db.query(School).filter(School.id == school_id).first()
        if school is None:
            raise ValueError("Ecole introuvable")

        # Verifier que l'utilisateur est membre
        member = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == user_id,
                SchoolMember.is_active == True,  # noqa: E712
            )
            .first()
        )
        if member is None:
            raise ValueError("Vous n'etes pas membre de cette ecole")

        # Obtenir les donnees d'engagement
        engagement_service = SchoolEngagementService(self.db, self.redis)
        engagement_data = engagement_service.calculer_engagement(school_id)

        # Obtenir les donnees de quota
        quota_service = SchoolQuotaService(self.db, self.redis)
        quota_stats = await quota_service.obtenir_stats_jour(school_id)

        return {
            "school": school.serialize_dashboard(is_admin=is_admin),
            "engagement": engagement_data,
            "quota": quota_stats,
        }

    # ─── Supprimer un membre ───────────────────────────────────────────

    async def supprimer_membre(
        self, school_id: str, target_user_id: str, admin_id: str
    ) -> dict:
        """Supprime un membre de l'ecole (admin uniquement)."""
        # Verifier que l'appelant est admin de l'ecole
        admin_member = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == admin_id,
                SchoolMember.role_ecole == "admin",
            )
            .first()
        )
        if admin_member is None:
            raise ValueError("Vous n'etes pas admin de cette ecole")

        # Recuperer le membre cible
        target_member = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == target_user_id,
            )
            .first()
        )
        if target_member is None:
            raise ValueError("Membre introuvable dans cette ecole")

        # Recuperer l'ecole
        school = self.db.query(School).filter(School.id == school_id).first()

        # Supprimer le membre
        self.db.delete(target_member)

        # Remettre l'utilisateur en freemium
        target_user = (
            self.db.query(User).filter(User.id == target_user_id).first()
        )
        if target_user:
            target_user.plan_effectif = "freemium"
            target_user.school_id = None

        # Mettre a jour le compteur d'eleves actifs
        if school and school.nb_eleves_actifs > 0:
            school.nb_eleves_actifs -= 1

        self.db.commit()

        return {
            "message": "Membre supprime avec succes",
            "school_id": school_id,
            "removed_user_id": str(target_user_id),
        }

    # ─── Supprimer une ecole ───────────────────────────────────────────

    async def supprimer_ecole(
        self, school_id: str, admin_id: str, confirmation: str
    ) -> dict:
        """Supprime une ecole et tous ses membres (admin uniquement)."""
        if confirmation != "SUPPRIMER":
            raise ValueError(
                "Confirmation requise: envoyez 'SUPPRIMER' pour confirmer la suppression"
            )

        # Verifier que l'appelant est admin de l'ecole
        admin_member = (
            self.db.query(SchoolMember)
            .filter(
                SchoolMember.school_id == school_id,
                SchoolMember.user_id == admin_id,
                SchoolMember.role_ecole == "admin",
            )
            .first()
        )
        if admin_member is None:
            raise ValueError("Vous n'etes pas admin de cette ecole")

        # Recuperer l'ecole
        school = self.db.query(School).filter(School.id == school_id).first()
        if school is None:
            raise ValueError("Ecole introuvable")

        # Remettre tous les membres en freemium
        members = (
            self.db.query(SchoolMember)
            .filter(SchoolMember.school_id == school_id)
            .all()
        )
        user_ids = []
        for member in members:
            user_ids.append(member.user_id)

        if user_ids:
            (
                self.db.query(User)
                .filter(User.id.in_(user_ids))
                .update(
                    {"plan_effectif": "freemium", "school_id": None},
                    synchronize_session="fetch",
                )
            )

        # Supprimer tous les membres
        (
            self.db.query(SchoolMember)
            .filter(SchoolMember.school_id == school_id)
            .delete(synchronize_session="fetch")
        )

        # Supprimer l'ecole
        self.db.delete(school)
        self.db.commit()

        return {
            "message": f"Ecole '{school.nom}' supprimee avec succes",
            "school_id": school_id,
            "members_removed": len(user_ids),
        }
