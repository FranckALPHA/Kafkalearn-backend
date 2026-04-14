from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, TIMESTAMP,
    CheckConstraint, Index, ForeignKey, func
)


class UserDocument(Base, TimestampMixin):
    __tablename__ = "user_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    titre = Column(String(255), nullable=False)
    subject = Column(String(100), nullable=True, index=True)
    class_name = Column(String(50), nullable=True)
    language = Column(
        String(5),
        default="fr",
        nullable=False
    )
    nom_fichier_original = Column(String(255), nullable=False)
    nom_fichier_stocke = Column(String(255), nullable=False, unique=True)
    file_url = Column(String(500), nullable=False)
    mimetype = Column(
        String(100),
        nullable=False
    )
    poids_octets = Column(Integer, nullable=False)
    nb_pages = Column(Integer, nullable=True)
    extracted_text = Column(Text, nullable=True)
    extraction_status = Column(
        String(15),
        default="pending",
        nullable=False
    )
    extraction_error = Column(Text, nullable=True)
    is_vectorized = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    vectorization_status = Column(
        String(15),
        default="pending",
        nullable=False
    )
    nb_chunks = Column(Integer, nullable=True)
    nb_utilisations_rag = Column(Integer, default=0, nullable=False)
    derniere_utilisation_at = Column(TIMESTAMP, nullable=True, index=True)
    hash_contenu = Column(String(64), nullable=True, index=True)

    __table_args__ = (
        CheckConstraint(
            "language IN ('fr', 'en')",
            name="ck_user_documents_language"
        ),
        CheckConstraint(
            "mimetype IN ('application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword')",
            name="ck_user_documents_mimetype"
        ),
        CheckConstraint(
            "poids_octets > 0",
            name="ck_user_documents_poids_octets"
        ),
        CheckConstraint(
            "nb_pages IS NULL OR nb_pages > 0",
            name="ck_user_documents_nb_pages"
        ),
        CheckConstraint(
            "extraction_status IN ('pending', 'processing', 'success', 'failed')",
            name="ck_user_documents_extraction_status"
        ),
        CheckConstraint(
            "vectorization_status IN ('pending', 'queued', 'processing', 'complete', 'failed')",
            name="ck_user_documents_vectorization_status"
        ),
        CheckConstraint(
            "nb_chunks >= 0",
            name="ck_user_documents_nb_chunks"
        ),
        CheckConstraint(
            "nb_utilisations_rag >= 0",
            name="ck_user_documents_nb_utilisations_rag"
        ),
        Index("idx_user_subject_created", "user_id", "subject", "created_at"),
        Index("idx_user_vectorized", "user_id", "is_vectorized"),
        Index("idx_user_extraction", "user_id", "extraction_status"),
        Index("idx_hash_user", "hash_contenu", "user_id"),
    )

    user = relationship("User")
    chunks = relationship(
        "UserDocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    @property
    def is_ready_for_rag(self) -> bool:
        return (
            self.extraction_status == "success"
            and self.is_vectorized
            and self.vectorization_status == "complete"
        )

    @property
    def is_ready_for_semantic_search(self) -> bool:
        return self.is_vectorized and self.vectorization_status == "complete"

    def serialize_list_item(self) -> dict:
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "titre": self.titre,
            "subject": self.subject,
            "class_name": self.class_name,
            "language": self.language,
            "nom_fichier_original": self.nom_fichier_original,
            "nom_fichier_stocke": self.nom_fichier_stocke,
            "file_url": self.file_url,
            "mimetype": self.mimetype,
            "poids_octets": self.poids_octets,
            "nb_pages": self.nb_pages,
            "extraction_status": self.extraction_status,
            "is_vectorized": self.is_vectorized,
            "vectorization_status": self.vectorization_status,
            "nb_chunks": self.nb_chunks,
            "nb_utilisations_rag": self.nb_utilisations_rag,
            "derniere_utilisation_at": self.derniere_utilisation_at.isoformat() if self.derniere_utilisation_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def serialize_detail(self, preview_chars: int = 300) -> dict:
        data = self.serialize_list_item()
        if self.extracted_text:
            data["extracted_text_preview"] = self.extracted_text[:preview_chars]
        else:
            data["extracted_text_preview"] = None
        data["extraction_error"] = self.extraction_error
        data["hash_contenu"] = self.hash_contenu
        return data
