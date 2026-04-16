from app.core.database import Base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    CheckConstraint,
    Index,
    ForeignKey,
    UniqueConstraint,
    TIMESTAMP,
    func
)
from sqlalchemy.orm import relationship


class UserDocumentChunk(Base):
    __tablename__ = "user_document_chunks"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("user_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    texte_chunk = Column(Text, nullable=False)
    chunk_idx = Column(Integer, nullable=False)
    is_embedded = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "chunk_idx >= 0",
            name="ck_user_document_chunks_chunk_idx"
        ),
        UniqueConstraint(
            "document_id", "chunk_idx",
            name="uq_user_document_chunk_idx"
        ),
        Index("idx_user_chunk", "user_id", "document_id"),
    )

    document = relationship("UserDocument", back_populates="chunks")

    def serialize_for_rag(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "user_id": str(self.user_id),
            "texte_chunk": self.texte_chunk,
            "chunk_idx": self.chunk_idx,
            "is_embedded": self.is_embedded,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
