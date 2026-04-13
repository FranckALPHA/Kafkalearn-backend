from sqlalchemy import Column, Integer, String, Text, Boolean, CheckConstraint, Index, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class MetadataQueue(Base, TimestampMixin):
    __tablename__ = "metadata_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    fichier_path = Column(String(500), nullable=False)
    texte_extrait_preview = Column(Text, nullable=True)
    raison_echec = Column(String(100), nullable=False)
    metadata_tentee = Column(JSONB, default=dict, nullable=True)
    nb_retries = Column(Integer, default=0)
    dernier_retry_at = Column(TIMESTAMP, nullable=True)
    is_resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    resolved_at = Column(TIMESTAMP, nullable=True)

    __table_args__ = (
        CheckConstraint("nb_retries >= 0", name="ck_metaq_nb_retries"),
        Index("idx_unresolved_created", "is_resolved", "created_at"),
        Index("idx_reason", "raison_echec"),
    )

    document = relationship("Document")
    resolver = relationship("User")

    def serialize_for_admin(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "fichier_path": self.fichier_path,
            "texte_extrait_preview": self.texte_extrait_preview,
            "raison_echec": self.raison_echec,
            "metadata_tentee": self.metadata_tentee,
            "nb_retries": self.nb_retries,
            "dernier_retry_at": self.dernier_retry_at.isoformat() if self.dernier_retry_at else None,
            "is_resolved": self.is_resolved,
            "resolved_by": str(self.resolved_by),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
