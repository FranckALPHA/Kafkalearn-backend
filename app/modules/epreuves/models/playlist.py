"""
models/playlist.py
==================
Entité Playlist — collections organisées de documents.
"""
import uuid

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class Playlist(Base, TimestampMixin):
    __tablename__ = "playlists"

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    nom = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    objectif = Column(String(100), nullable=True)

    # ─── Contenu ─────────────────────────────────────────────────
    nb_documents = Column(Integer, default=0, nullable=False)

    # ─── Partage & visibilité ────────────────────────────────────
    is_public = Column(Boolean, default=False, nullable=False, index=True)
    lien_partage = Column(String(20), unique=True, nullable=True)
    nb_copies = Column(Integer, default=0, nullable=False)

    # ─── État & ciblage ──────────────────────────────────────────
    is_archived = Column(Boolean, default=False, nullable=False)
    matiere_cible = Column(String(100), nullable=True)
    niveau_cible = Column(String(50), nullable=True)

    # ─── Relations ───────────────────────────────────────────────
    items = relationship(
        "PlaylistDocument", back_populates="playlist",
        cascade="all, delete-orphan"
    )
    user = relationship("User")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_playlist_user_updated", "user_id", "updated_at"),
        Index("idx_public", "is_public", "created_at"),
    )

    # ─── Sérialisation ───────────────────────────────────────────
    def serialize_list_item(self) -> dict:
        """Sérialisation légère pour les listes."""
        return {
            "id": self.id,
            "nom": self.nom,
            "objectif": self.objectif,
            "nb_documents": self.nb_documents,
            "is_public": self.is_public,
            "matiere_cible": self.matiere_cible,
            "niveau_cible": self.niveau_cible,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def serialize_detail(self) -> dict:
        """Sérialisation complète pour le détail."""
        return {
            **self.serialize_list_item(),
            "user_id": str(self.user_id),
            "description": self.description,
            "lien_partage": self.lien_partage,
            "nb_copies": self.nb_copies,
            "is_archived": self.is_archived,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Playlist(id={self.id}, nom='{self.nom}', user_id={self.user_id})>"
