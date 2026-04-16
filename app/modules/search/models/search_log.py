"""
models/search_log.py
====================
Journal complet de chaque recherche, source principale d'analytics.
"""
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    SMALLINT,
    CheckConstraint,
    Index,
    ForeignKey,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class SearchLog(Base):
    __tablename__ = "search_logs"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identifiants ────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)

    # ─── Requête utilisateur ─────────────────────────────────────
    texte_requete = Column(Text, nullable=False)
    texte_normalise = Column(Text, nullable=True)

    # ─── Détection intention ─────────────────────────────────────
    intention_detectee = Column(
        String(20),
        CheckConstraint("intention_detectee IN ('explication','entrainement','general')"),
        nullable=True,
    )
    methode_detection = Column(
        String(10),
        CheckConstraint("methode_detection IN ('regex','llm','fallback')"),
        nullable=True,
    )

    # ─── Filtres appliqués ───────────────────────────────────────
    matiere_filtre = Column(String(100), nullable=True)
    matiere_detectee = Column(String(100), nullable=True, index=True)
    niveau_filtre = Column(String(50), nullable=True)
    serie_filtre = Column(String(20), nullable=True)
    annee_filtre = Column(Integer, nullable=True)
    type_doc_filtre = Column(String(20), nullable=True)

    # ─── Paramètres de recherche ─────────────────────────────────
    top_k_demande = Column(Integer, default=10, nullable=False)
    nb_chunks_retournes = Column(Integer, default=0, nullable=False)
    nb_sources_distinctes = Column(Integer, default=0, nullable=False)

    # ─── Réponse IA ──────────────────────────────────────────────
    reponse_ia_generee = Column(Boolean, default=False, nullable=False)
    mode_ia = Column(String(25), nullable=True)
    erreur_ia = Column(String(50), nullable=True)
    quota_consomme = Column(Boolean, default=False, nullable=False)

    # ─── Métriques performance ───────────────────────────────────
    score_semantique_max = Column(Float, nullable=True)
    latence_vectorisation_ms = Column(Integer, nullable=True)
    latence_vespa_ms = Column(Integer, nullable=True)
    latence_llm_ms = Column(Integer, nullable=True)
    latence_totale_ms = Column(Integer, nullable=True, index=True)

    # ─── Feedback utilisateur ────────────────────────────────────
    feedback_rating = Column(
        SMALLINT, CheckConstraint("feedback_rating BETWEEN 1 AND 5"), nullable=True
    )
    feedback_commentaire = Column(Text, nullable=True)

    # ─── Relations ───────────────────────────────────────────────
    chunks_retournes = relationship(
        "SearchChunkReturned", back_populates="search_log",
        lazy="dynamic", cascade="all, delete-orphan"
    )
    user = relationship("User")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_search_user_created", "user_id", "created_at"),
        Index("idx_matiere_intention", "matiere_detectee", "intention_detectee"),
        Index("idx_perf_ia", "reponse_ia_generee", "latence_totale_ms"),
        Index("idx_feedback", "feedback_rating", "created_at"),
    )

    # ─── Méthodes utilitaires ────────────────────────────────────
    @property
    def est_anonyme(self) -> bool:
        return self.user_id is None

    def serialize_minimal(self) -> dict:
        """Pour l'historique utilisateur."""
        return {
            "id": self.id,
            "texte_requete": self.texte_requete,
            "intention_detectee": self.intention_detectee,
            "matiere_detectee": self.matiere_detectee,
            "nb_resultats": self.nb_chunks_retournes,
            "reponse_ia_generee": self.reponse_ia_generee,
            "feedback_rating": self.feedback_rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<SearchLog(id={self.id}, user_id={self.user_id}, requete='{self.texte_requete[:30]}')>"
