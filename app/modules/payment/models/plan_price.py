"""
models/plan_price.py
====================
Grille tarifaire des plans — source unique de vérité pour les prix.
"""
from sqlalchemy import Column, String, Integer, Boolean, CheckConstraint

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class PlanPrice(Base, TimestampMixin):
    __tablename__ = "plan_prices"

    # ─── Identité ────────────────────────────────────────────────
    plan_id = Column(String(20), primary_key=True)

    # ─── Tarification ───────────────────────────────────────────
    prix_fcfa = Column(Integer, CheckConstraint("prix_fcfa >= 0"), nullable=False)

    # ─── Quotas ──────────────────────────────────────────────────
    quota_type = Column(
        String(10),
        CheckConstraint("quota_type IN ('monthly','daily')"),
        nullable=False,
    )
    quota_valeur = Column(Integer, CheckConstraint("quota_valeur >= 0"), nullable=False)

    # ─── Duree ───────────────────────────────────────────────────
    duree_jours = Column(
        Integer,
        CheckConstraint("duree_jours > 0"),
        default=30,
        nullable=False,
    )

    # ─── Activation ──────────────────────────────────────────────
    is_active = Column(Boolean, default=True, nullable=False)

    # ─── Propriétés ─────────────────────────────────────────────
    @property
    def quota_par_jour(self) -> int:
        """Calcule le quota moyen par jour."""
        if self.quota_type == "daily":
            return self.quota_valeur
        if self.duree_jours and self.duree_jours > 0:
            return self.quota_valeur // self.duree_jours
        return 0

    # ─── Méthodes utilitaires ───────────────────────────────────
    def serialize_for_api(self) -> dict:
        """Sérialisation pour l'API publique des plans."""
        plan_names = {
            "freemium": "Freemium",
            "access": "Accès",
            "premium": "Premium",
            "pro": "Pro",
            "unlimited": "Illimité",
            "school": "École",
        }

        plan_features: dict[str, list[str]] = {
            "freemium": ["Accès limité aux quiz", "Suivi de progression basique"],
            "access": ["Accès complet aux quiz", "Statistiques détaillées"],
            "premium": [
                "Accès illimité aux quiz",
                "Analyses avancées",
                "Support prioritaire",
            ],
            "pro": [
                "Tout Premium",
                "Mode hors-ligne",
                "Personnalisation avancée",
            ],
            "unlimited": [
                "Tout Pro",
                "Accès multi-utilisateurs",
                "API dédiée",
            ],
            "school": [
                "Tableau de bord école",
                "Gestion des sièges",
                "Rapports consolidés",
                "Support dédié",
            ],
        }

        return {
            "id": self.plan_id,
            "nom": plan_names.get(self.plan_id, "Inconnu"),
            "prix_fcfa": self.prix_fcfa,
            "quota_ia": self.quota_valeur,
            "quota_type": self.quota_type,
            "fonctionnalites": plan_features.get(self.plan_id, []),
            "is_active": self.is_active,
        }

    def __repr__(self) -> str:
        return (
            f"<PlanPrice(plan_id={self.plan_id}, prix_fcfa={self.prix_fcfa}, "
            f"is_active={self.is_active})>"
        )
