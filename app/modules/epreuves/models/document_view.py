"""
models/document_view.py
=======================
Entité DocumentView — traçage des consultations et téléchargements.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, TIMESTAMP, CheckConstraint,
    ForeignKey, Index, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.modules.users.models.mixins import TimestampMixin


class DocumentView(Base, TimestampMixin):
    __tablename__ = "document_views"

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)

    # ─── Contexte ────────────────────────────────────────────────
    source = Column(
        String(20),
        CheckConstraint("source IN ('view', 'download', 'recommendation', 'search')"),
        default="view",
        nullable=False
    )
    created_at = Column(TIMESTAMP, default=func.now(), nullable=False)

    # ─── Engagement ──────────────────────────────────────────────
    duree_consultation_sec = Column(Integer, nullable=True)
    a_scrolle = Column(Boolean, default=False, nullable=False)

    # ─── Relations ───────────────────────────────────────────────
    document = relationship("Document", back_populates="views")
    user = relationship("User", back_populates="document_views")

    # ─── Index composites ────────────────────────────────────────
    __table_args__ = (
        Index("idx_doc_created", "document_id", "created_at"),
        Index("idx_user_doc", "user_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentView(id={self.id}, document_id={self.document_id}, source='{self.source}')>"
