"""
models/asset_rating.py
======================
Modele AssetRating pour les evaluations des assets pedagogiques.
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    CheckConstraint,
    Index,
    ForeignKey,
    UniqueConstraint,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class AssetRating(Base):
    __tablename__ = "asset_ratings"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identite ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(
        Integer,
        ForeignKey("pedagogical_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    note = Column(
        Integer,
        CheckConstraint("note BETWEEN 1 AND 5"),
        nullable=False
    )
    commentaire = Column(String(500), nullable=True)

    # ─── Relations ───────────────────────────────────────────────
    asset = relationship("PedagogicalAsset", back_populates="ratings")
    user = relationship("User")

    # ─── Contraintes & index ─────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("asset_id", "user_id", name="uq_asset_user_rating"),
        Index("idx_asset_note", "asset_id", "note"),
    )

    # ─── Methodes ────────────────────────────────────────────────
    def serialize(self) -> dict:
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "user_id": str(self.user_id),
            "note": self.note,
            "commentaire": self.commentaire,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<AssetRating(id={self.id}, asset={self.asset_id}, note={self.note})>"
