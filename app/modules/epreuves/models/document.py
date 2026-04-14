"""
models/document.py
==================
Entité Document — métadonnées des épreuves et documents pédagogiques.
"""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, ForeignKey,
    Index, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    nom_original = Column(String(255), nullable=False)
    nom_affiche = Column(String(255), nullable=True)
    chemin_final = Column(String(500), nullable=False)
    mimetype = Column(String(50), nullable=False)
    poids_octets = Column(Integer, nullable=False)
    hash_contenu = Column(String(64), unique=True, nullable=False, index=True)

    # ─── Classification ──────────────────────────────────────────
    matiere = Column(String(100), nullable=False, index=True)
    niveau = Column(String(50), nullable=False, index=True)
    serie = Column(String(20), nullable=True, index=True)
    annee = Column(Integer, nullable=False, index=True)
    type_doc = Column(String(50), nullable=False, index=True)
    sous_type = Column(String(50), nullable=True)
    notion_principale = Column(String(200), nullable=True)

    # ─── Contenu & recherche ─────────────────────────────────────
    mots_cles = Column(JSONB, default=list)
    texte_extrait = Column(Text, nullable=True)

    # ─── Pipeline IA ─────────────────────────────────────────────
    is_embedded = Column(Boolean, default=False, nullable=False)
    etablissement = Column(String(255), nullable=True)
    region = Column(String(100), nullable=True)
    partie = Column(String(50), nullable=True)
    duree = Column(Integer, nullable=True)
    coefficient = Column(Integer, nullable=True)
    total_points = Column(Integer, nullable=True)
    langue = Column(String(5), default="fr", nullable=False)
    difficulte_estimee = Column(
        String(10),
        CheckConstraint("difficulte_estimee IN ('facile','moyen','difficile')"),
        nullable=True
    )
    is_validated = Column(Boolean, default=False, nullable=False, index=True)

    # ─── Propriétaire ────────────────────────────────────────────
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # ─── Pipeline & confiance ────────────────────────────────────
    metadata_confidence = Column(Float, nullable=True)
    ingest_status = Column(
        String(20),
        CheckConstraint("ingest_status IN ('pending','processing','completed','failed')"),
        default="pending",
        nullable=False
    )

    # ─── Statistiques ────────────────────────────────────────────
    nb_vues = Column(Integer, default=0, nullable=False)
    nb_telechargements = Column(Integer, default=0, nullable=False)
    nb_favoris = Column(Integer, default=0, nullable=False)
    nb_tentatives_ia = Column(Integer, default=0, nullable=False)
    score_moyen_utilisateurs = Column(Float, nullable=True)

    # ─── Relations ───────────────────────────────────────────────
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    playlist_items = relationship("PlaylistDocument", back_populates="document", cascade="all, delete-orphan")
    views = relationship("DocumentView", back_populates="document", cascade="all, delete-orphan")
    analyses = relationship("DocumentAnalysis", back_populates="document", cascade="all, delete-orphan")
    user = relationship("User")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_search_main", "matiere", "niveau", "serie", "annee"),
        Index("idx_pipeline", "type_doc", "is_embedded", "ingest_status"),
        Index("idx_document_popularity", "nb_vues", "created_at"),
        Index("idx_validated_matiere", "is_validated", "matiere"),
    )

    # ─── Propriétés ──────────────────────────────────────────────
    @property
    def is_ready_for_search(self) -> bool:
        """Le document est-il prêt pour la recherche vectorielle ?"""
        return self.is_embedded and self.is_validated and self.ingest_status == "completed"

    @property
    def download_available(self) -> bool:
        """Le téléchargement est-il disponible ?"""
        return self.is_validated and bool(self.chemin_final)

    # ─── Sérialisation ───────────────────────────────────────────
    def serialize_list_item(self) -> dict:
        """Sérialisation légère pour les listes."""
        return {
            "id": self.id,
            "nom_original": self.nom_original,
            "nom_affiche": self.nom_affiche,
            "matiere": self.matiere,
            "niveau": self.niveau,
            "serie": self.serie,
            "annee": self.annee,
            "type_doc": self.type_doc,
            "sous_type": self.sous_type,
            "is_embedded": self.is_embedded,
            "is_validated": self.is_validated,
            "nb_vues": self.nb_vues,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def serialize_detail(self) -> dict:
        """Sérialisation complète pour le détail."""
        return {
            **self.serialize_list_item(),
            "chemin_final": self.chemin_final,
            "mimetype": self.mimetype,
            "poids_octets": self.poids_octets,
            "notion_principale": self.notion_principale,
            "mots_cles": self.mots_cles,
            "texte_extrait": self.texte_extrait,
            "etablissement": self.etablissement,
            "region": self.region,
            "partie": self.partie,
            "duree": self.duree,
            "coefficient": self.coefficient,
            "total_points": self.total_points,
            "langue": self.langue,
            "difficulte_estimee": self.difficulte_estimee,
            "metadata_confidence": self.metadata_confidence,
            "ingest_status": self.ingest_status,
            "nb_telechargements": self.nb_telechargements,
            "nb_favoris": self.nb_favoris,
            "nb_tentatives_ia": self.nb_tentatives_ia,
            "score_moyen_utilisateurs": self.score_moyen_utilisateurs,
            "is_ready_for_search": self.is_ready_for_search,
            "download_available": self.download_available,
            "uploaded_by": str(self.uploaded_by) if self.uploaded_by else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, nom='{self.nom_original}', matiere='{self.matiere}')>"
