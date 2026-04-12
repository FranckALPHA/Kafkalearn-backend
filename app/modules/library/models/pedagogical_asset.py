"""
models/pedagogical_asset.py
===========================
Modele PedagogicalAsset pour le module library.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, CheckConstraint,
    Index, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class PedagogicalAsset(Base, TimestampMixin):
    __tablename__ = "pedagogical_assets"

    # ─── Identite ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # ─── Metadonnees ─────────────────────────────────────────────
    titre = Column(String(255), nullable=False, index=True)
    asset_type = Column(
        String(20),
        CheckConstraint(
            "asset_type IN ('FICHE','QUIZ','CORRIGE','EPREUVE','SOLVER','MEMORY_PACK','VISUALISATION')"
        ),
        nullable=False
    )
    subject = Column(String(100), nullable=False, index=True)
    class_name = Column("class_name", String(50), nullable=False, index=True)
    serie = Column(String(20), nullable=True)
    notion = Column(String(255), nullable=True)

    # ─── Plan & langue ───────────────────────────────────────────
    required_plan = Column(
        String(20),
        CheckConstraint(
            "required_plan IN ('freemium','access','premium','pro','unlimited','school')"
        ),
        default="access",
        nullable=False
    )
    langue = Column(
        String(5),
        CheckConstraint("langue IN ('fr','en','both')"),
        default="fr",
        nullable=False
    )

    # ─── Contenu & fichier ───────────────────────────────────────
    content_json = Column(JSONB, nullable=True)
    file_url = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    source_doc_id = Column(Integer, nullable=True)

    # ─── Generation ──────────────────────────────────────────────
    generation_status = Column(
        String(15),
        CheckConstraint(
            "generation_status IN ('pending','generating','complete','failed')"
        ),
        default="complete",
        nullable=False
    )

    # ─── Visibilite & partage ────────────────────────────────────
    is_public = Column(Boolean, default=False, index=True)
    lien_partage = Column(String(20), unique=True, nullable=True, index=True)

    # ─── Statistiques ────────────────────────────────────────────
    nb_vues = Column(Integer, CheckConstraint("nb_vues >= 0"), default=0)
    nb_telechargements = Column(Integer, CheckConstraint("nb_telechargements >= 0"), default=0)
    nb_copies = Column(Integer, CheckConstraint("nb_copies >= 0"), default=0)
    note_moyenne = Column(Float, nullable=True)
    nb_notes = Column(Integer, CheckConstraint("nb_notes >= 0"), default=0)

    # ─── Relations ───────────────────────────────────────────────
    user = relationship("User", back_populates="pedagogical_assets")
    ratings = relationship(
        "AssetRating",
        back_populates="asset",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    copies_as_original = relationship(
        "AssetCopy",
        foreign_keys="AssetCopy.original_asset_id",
        back_populates="original",
        lazy="dynamic"
    )
    copies_as_copy = relationship(
        "AssetCopy",
        foreign_keys="AssetCopy.copy_asset_id",
        back_populates="copy",
        lazy="dynamic"
    )

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_user_type_subject", "user_id", "asset_type", "subject"),
        Index("idx_public_explore", "is_public", "asset_type", "subject", "note_moyenne"),
        Index("idx_user_created", "user_id", "created_at"),
        Index("idx_share_code", "lien_partage"),
    )

    # ─── Proprietes ──────────────────────────────────────────────
    @property
    def is_downloadable(self) -> bool:
        """Un asset est telechargeable s'il a un fichier et un statut complet."""
        return bool(self.file_url and self.generation_status == "complete")

    @property
    def can_be_copied(self) -> bool:
        """Un asset peut etre copie s'il est public ou si l'utilisateur est le proprietaire."""
        return self.is_public or self.generation_status == "complete"

    # ─── Methodes de serialisation ───────────────────────────────
    def serialize_list_item(self, is_owner: bool = False, mask_author: bool = True) -> dict:
        """Serialisation pour les vues en liste."""
        author_name = "Anonyme"
        if self.user:
            if mask_author and not is_owner:
                author_name = self.user.prenom[:3] + "***" if self.user.prenom else "Anonyme"
            else:
                author_name = f"{self.user.prenom} {self.user.nom}" if self.user.prenom and self.user.nom else (self.user.prenom or "Anonyme")

        return {
            "id": self.id,
            "titre": self.titre,
            "asset_type": self.asset_type,
            "subject": self.subject,
            "class_name": self.class_name,
            "serie": self.serie,
            "notion": self.notion,
            "langue": self.langue,
            "is_public": self.is_public,
            "lien_partage": self.lien_partage,
            "nb_vues": self.nb_vues,
            "nb_telechargements": self.nb_telechargements,
            "nb_copies": self.nb_copies,
            "note_moyenne": self.note_moyenne,
            "nb_notes": self.nb_notes,
            "author": author_name,
            "generation_status": self.generation_status,
            "file_url": self.file_url if is_owner else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def serialize_detail(self, is_owner: bool = False, user_note: int = None) -> dict:
        """Serialisation pour la vue detaillee d'un asset."""
        data = self.serialize_list_item(is_owner=is_owner, mask_author=not is_owner)
        data.update({
            "user_id": str(self.user_id) if self.user_id else None,
            "required_plan": self.required_plan,
            "content_json": self.content_json if is_owner else None,
            "file_size_bytes": self.file_size_bytes,
            "source_doc_id": self.source_doc_id,
            "is_downloadable": self.is_downloadable,
            "can_be_copied": self.can_be_copied,
            "user_note": user_note,
        })
        return data

    def __repr__(self) -> str:
        return f"<PedagogicalAsset(id={self.id}, titre='{self.titre}', type='{self.asset_type}')>"
