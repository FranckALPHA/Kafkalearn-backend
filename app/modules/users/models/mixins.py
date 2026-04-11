"""
models/mixins.py
================
Mixins réutilisables pour toutes les entités du module users.
"""
from sqlalchemy import Column, TIMESTAMP, Boolean, func


class TimestampMixin:
    """Ajoute created_at / updated_at automatiquement."""
    created_at = Column(TIMESTAMP, default=func.now(), nullable=False, index=True)
    updated_at = Column(
        TIMESTAMP, default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """
    Suppression logique (RGPD, audit, récupération).
    Toutes les requêtes doivent filtrer sur is_deleted == False.
    """
    deleted_at = Column(TIMESTAMP, nullable=True, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    def soft_delete(self):
        """Marque l'entité comme supprimée sans effacer les données."""
        self.is_deleted = True
        self.deleted_at = func.now()

    def restore(self):
        """Restaure une entité précédemment supprimée."""
        self.is_deleted = False
        self.deleted_at = None
