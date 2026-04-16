"""
models/concept_graph.py
=======================
Graphe cognitif : concepts, relations, prérequis.
Deux couches :
  - Globale (user_id = NULL) : prérequis du programme scolaire
  - Personnelle (user_id = UUID) : lacunes, maîtrises de l'utilisateur
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# ─── Types de relations ──────────────────────────────────────────
RELATION_TYPES = [
    "PRE_REQUIS_DE",   # Global : source est prérequis de target
    "A_ECHOUE_SUR",    # Personnel : utilisateur a échoué sur ce concept
    "MAITRISE",        # Personnel : utilisateur maîtrise ce concept
    "EN_COURS",        # Personnel : utilisateur travaille ce concept
    "LIEN_FAIBLE",     # Personnel/Global : lien sémantique faible détecté
]


class ConceptGraph(Base):
    __tablename__ = "concept_graph"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identité ────────────────────────────────────────────────
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # user_id = NULL → arête globale (programme scolaire)
    # user_id = UUID → arête personnelle
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # ─── Arête du graphe ─────────────────────────────────────────
    source = Column(String(200), nullable=False, index=True)    # "derivees"
    target = Column(String(200), nullable=False, index=True)    # "integrales"
    relation = Column(String(30), nullable=False, index=True)   # PRE_REQUIS_DE, A_ECHOUE_SUR, etc.

    # ─── Métadonnées ─────────────────────────────────────────────
    confidence = Column(Float, default=1.0, nullable=False)      # 0.0-1.0
    source_type = Column(String(30), nullable=False)             # 'manual', 'quiz', 'chat', 'document_analysis', 'human_validated', 'human_resolved', 'inference', 'migration'
    matiere = Column(String(100), nullable=True, index=True)     # "Mathematiques"
    context = Column(Text, nullable=True)                        # JSON: {"document_id": 42, "evidence": "..."}

    # Nom canonique pour la déduplication sémantique
    # Toutes les variantes ("dérivées", "derivees", "calcul différentiel")
    # pointent vers le même canonical_name
    canonical_name = Column(String(200), nullable=True, index=True)

    # ─── Relation ────────────────────────────────────────────────
    user = relationship("User", back_populates="concept_edges")

    # ─── Contraintes & Index ─────────────────────────────────────
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0.0 AND 1.0", name="chk_confidence_range"),
        CheckConstraint(
            f"relation IN {tuple(RELATION_TYPES)}",
            name="chk_relation_type",
        ),
        CheckConstraint(
            "source_type IN ('manual', 'quiz', 'chat', 'inference', 'migration')",
            name="chk_source_type",
        ),
        # Pas de doublon d'arête
        UniqueConstraint(
            "user_id", "source", "target", "relation",
            name="uq_concept_graph_edge",
        ),
        # Index pour traversées de graphe
        Index("idx_cg_user_source", "user_id", "source"),
        Index("idx_cg_user_target", "user_id", "target"),
        Index("idx_cg_user_relation", "user_id", "relation"),
        Index("idx_cg_matiere", "user_id", "matiere"),
        # Index partiel pour le graphe global (user_id IS NULL)
        Index("idx_cg_global_edges", "source", "target",
              postgresql_where=func.coalesce(user_id, "00000000-0000-0000-0000-000000000000")
              == "00000000-0000-0000-0000-000000000000"),
    )

    # ─── Méthodes ────────────────────────────────────────────────
    def serialize(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "confidence": self.confidence,
            "source_type": self.source_type,
            "matiere": self.matiere,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def serialize_minimal(self) -> dict:
        """Sérialisation légère pour les listes."""
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "confidence": self.confidence,
            "matiere": self.matiere,
        }

    def __repr__(self) -> str:
        user_str = str(self.user_id)[:8] if self.user_id else "GLOBAL"
        return (
            f"<ConceptGraph({user_str}): {self.source} -[{self.relation}]-> {self.target}>"
        )
