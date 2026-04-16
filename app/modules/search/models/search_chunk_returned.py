"""
models/search_chunk_returned.py
===============================
Détail des chunks retournés pour chaque recherche (analytics granulaires).
"""
from sqlalchemy import (
    Column,
    Integer,
    Float,
    Boolean,
    SMALLINT,
    Index,
    ForeignKey,
    TIMESTAMP,
    func
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class SearchChunkReturned(Base):
    __tablename__ = "search_chunks_retournes"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    id = Column(Integer, primary_key=True, autoincrement=True)
    search_log_id = Column(
        Integer, ForeignKey("search_logs.id"), nullable=False, index=True
    )

    # Références vers le contenu
    chunk_id = Column(Integer, nullable=False)
    document_id = Column(Integer, nullable=False)

    # Position et scoring
    rang_retourne = Column(SMALLINT, nullable=False)
    score_ann = Column(Float, nullable=True)
    score_bm25 = Column(Float, nullable=True)
    score_rrf = Column(Float, nullable=True)

    # Usage dans la réponse LLM
    est_cite_dans_reponse = Column(Boolean, default=False, nullable=False)

    # Relation
    search_log = relationship("SearchLog", back_populates="chunks_retournes")

    # Index pour analytics
    __table_args__ = (
        Index("idx_chunk_usage", "chunk_id", "est_cite_dans_reponse"),
        Index("idx_doc_popularity", "document_id", "rang_retourne"),
    )

    def __repr__(self) -> str:
        return f"<SearchChunkReturned(log_id={self.search_log_id}, chunk={self.chunk_id}, rang={self.rang_retourne})>"
