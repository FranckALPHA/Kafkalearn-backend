"""
models/transaction.py
=====================
Entité Transaction — paiements et transferts, traçabilité complète.
"""
from sqlalchemy import (
    Column, String, Integer, TIMESTAMP, CheckConstraint, Index, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import secrets
import string

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    # ─── Identité ────────────────────────────────────────────────
    id = Column(String(20), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # ─── Montant & devise ────────────────────────────────────────
    amount = Column(Integer, CheckConstraint("amount > 0"), nullable=False)
    currency = Column(String(5), default="XAF", nullable=False)

    # ─── Plan ───────────────────────────────────────────────────
    plan_id = Column(
        String(20),
        CheckConstraint(
            "plan_id IN ('freemium','access','premium','pro','unlimited','school')"
        ),
        nullable=True,
    )
    plan_precedent = Column(String(20), nullable=True)

    # ─── Type & statut ──────────────────────────────────────────
    type = Column(
        String(10),
        CheckConstraint("type IN ('payment','transfer')"),
        nullable=False,
    )
    status = Column(
        String(15),
        CheckConstraint(
            "status IN ('pending','processing','complete','failed','canceled')"
        ),
        default="pending",
        nullable=False,
        index=True,
    )

    # ─── Fournisseur & canal ────────────────────────────────────
    provider = Column(String(15), default="notchpay", nullable=False)
    channel = Column(String(20), nullable=True)  # cm.mtn, cm.orange
    beneficiary = Column(String(50), nullable=True)  # Téléphone pour les transferts

    # ─── Références passerelle ──────────────────────────────────
    gateway_ref = Column(String(100), unique=True, nullable=True, index=True)  # NotchPay ID
    raw_data = Column(JSONB, default=dict, nullable=True)

    # ─── École (plan school) ────────────────────────────────────
    school_id = Column(String(8), ForeignKey("schools.id"), nullable=True)
    nb_sieges = Column(Integer, nullable=True)

    # ─── Source du déclencheur ──────────────────────────────────
    source_declencheur = Column(
        String(20),
        CheckConstraint(
            "source_declencheur IN ('direct','referral_reward','school_renewal','promo')"
        ),
        nullable=True,
    )

    # ─── Webhook retry tracking ─────────────────────────────────
    nb_tentatives_webhook = Column(
        Integer,
        CheckConstraint("nb_tentatives_webhook >= 0"),
        default=0,
    )
    dernier_webhook_at = Column(TIMESTAMP, nullable=True)

    # ─── Relations ORM ──────────────────────────────────────────
    user = relationship("User")
    school = relationship("School", back_populates="transactions")

    # ─── Index composites ───────────────────────────────────────
    __table_args__ = (
        Index("idx_user_status_date", "user_id", "status", "created_at"),
        Index("idx_pending_created", "status", "created_at"),
        Index("idx_school_type", "school_id", "type"),
    )

    # ─── Propriétés ─────────────────────────────────────────────
    @property
    def is_complete(self) -> bool:
        """Retourne True si la transaction est finalisée."""
        return self.status == "complete"

    @property
    def is_pending_too_long(self) -> bool:
        """Vérifie si une transaction est en attente depuis plus de 2h."""
        if self.status != "pending" or self.created_at is None:
            return False
        from datetime import timedelta, timezone
        now = func.now() if not self.created_at.tzinfo else func.now().replace(tzinfo=timezone.utc)
        return (now - self.created_at) > timedelta(hours=2)

    # ─── Méthodes utilitaires ───────────────────────────────────
    def serialize_for_history(self) -> dict:
        """Sérialisation pour l'historique des transactions utilisateur."""
        return {
            "id": self.id,
            "amount": self.amount,
            "currency": self.currency,
            "plan_id": self.plan_id,
            "plan_name": self._get_plan_name(),
            "type": self.type,
            "status": self.status,
            "provider": self.provider,
            "channel": self.channel,
            "beneficiary": self.beneficiary,
            "gateway_ref": self.gateway_ref,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def _get_plan_name(self) -> str:
        """Retourne le nom lisible du plan."""
        plan_names = {
            "freemium": "Freemium",
            "access": "Accès",
            "premium": "Premium",
            "pro": "Pro",
            "unlimited": "Illimité",
            "school": "École",
        }
        return plan_names.get(self.plan_id, "Inconnu") if self.plan_id else "N/A"

    @staticmethod
    def _generate_reference(prefix: str = "TRX") -> str:
        """Génère une référence unique de type TRX-XXXXXXXX (8 caractères alphanumériques)."""
        alphabet = string.ascii_uppercase + string.digits
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        return f"{prefix}-{code}"

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, user_id={self.user_id}, "
            f"amount={self.amount}, status={self.status})>"
        )
