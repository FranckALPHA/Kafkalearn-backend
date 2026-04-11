"""
models/playlist_document.py
============================
Table de jonction PlaylistDocument — association playlist ↔ document.
"""
from sqlalchemy import (
    Column, Integer, ForeignKey, TIMESTAMP, UniqueConstraint, func
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PlaylistDocument(Base):
    __tablename__ = "playlist_documents"

    # ─── Identité ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    playlist_id = Column(
        Integer, ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    position = Column(Integer, default=0, nullable=False)
    added_at = Column(TIMESTAMP, default=func.now(), nullable=False)

    # ─── Relations ───────────────────────────────────────────────
    playlist = relationship("Playlist", back_populates="items")
    document = relationship("Document", back_populates="playlist_items")

    # ─── Contraintes ─────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("playlist_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<PlaylistDocument(playlist_id={self.playlist_id}, document_id={self.document_id})>"
