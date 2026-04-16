"""
models/asset_copy.py
====================
Modele AssetCopy pour le suivi des copies d'assets pedagogiques.
"""
from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    Index,
    UniqueConstraint,
    TIMESTAMP,
    func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class AssetCopy(Base):
    __tablename__ = "asset_copies"

    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    # ─── Identite ────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_asset_id = Column(
        Integer,
        ForeignKey("pedagogical_assets.id"),
        nullable=False,
        index=True
    )
    copy_asset_id = Column(
        Integer,
        ForeignKey("pedagogical_assets.id"),
        nullable=False,
        unique=True
    )
    copied_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # ─── Relations ───────────────────────────────────────────────
    original = relationship(
        "PedagogicalAsset",
        foreign_keys=[original_asset_id],
        back_populates="copies_as_original"
    )
    copy = relationship(
        "PedagogicalAsset",
        foreign_keys=[copy_asset_id],
        back_populates="copies_as_copy"
    )

    # ─── Contraintes & index ─────────────────────────────────────
    __table_args__ = (
        UniqueConstraint("original_asset_id", "copied_by", name="uq_original_copied_by"),
    )

    def __repr__(self) -> str:
        return f"<AssetCopy(id={self.id}, original={self.original_asset_id}, copy={self.copy_asset_id})>"
