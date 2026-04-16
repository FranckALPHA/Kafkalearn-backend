"""
models/document_chunk.py
========================
Entité DocumentChunk — fragments de texte indexés pour le RAG.
"""

from sqlalchemy import (
    Column,
    Integer,
    Text,
    Boolean,
    ForeignKey,
    Index,
    TIMESTAMP,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    created_at = Column(TIMESTAMP, default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP, default=func.now(), onupdate=func.now(), nullable=False
    )

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    texte_chunk = Column(Text, nullable=False)
    chunk_idx = Column(Integer, nullable=False)
    nb_tokens_estime = Column(Integer, nullable=True)

    # ─── État & usage ────────────────────────────────────────────
    is_embedded = Column(Boolean, default=False, nullable=False, index=True)
    nb_fois_retourne = Column(Integer, default=0, nullable=False)
    nb_fois_cite = Column(Integer, default=0, nullable=False)

    # ─── Relations ───────────────────────────────────────────────
    document = relationship("Document", back_populates="chunks")

    # ─── Contraintes & index ─────────────────────────────────────
    __table_args__ = (
        Index("idx_document_chunk_unique", "doc_id", "chunk_idx", unique=True),
    )

    # ─── Sérialisation ───────────────────────────────────────────
    def serialize_for_rag(self) -> dict:
        """Sérialisation pour le contexte RAG."""
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "texte_chunk": self.texte_chunk,
            "chunk_idx": self.chunk_idx,
            "nb_tokens_estime": self.nb_tokens_estime,
            "is_embedded": self.is_embedded,
            "nb_fois_retourne": self.nb_fois_retourne,
            "nb_fois_cite": self.nb_fois_cite,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id}, doc_id={self.doc_id}, idx={self.chunk_idx})>"
        )
