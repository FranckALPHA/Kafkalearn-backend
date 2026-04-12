"""
services/asset_rating_service.py
=================================
Service pour la gestion des notes et evaluations des assets.
"""
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.library.models import PedagogicalAsset, AssetRating

from .base import LibraryBaseService

logger = logging.getLogger(__name__)


class AssetRatingService(LibraryBaseService):
    # ─────────────────────────────────────────────────────────────
    # Noter un asset
    # ─────────────────────────────────────────────────────────────
    async def noter_asset(
        self,
        asset_id: int,
        user_id,
        note: int,
        commentaire: str = None,
    ) -> dict:
        """Verifie que l'asset est public et que l'utilisateur n'est pas le proprietaire, puis cree/met a jour la note."""
        asset = (
            self.db.query(PedagogicalAsset)
            .filter(PedagogicalAsset.id == asset_id)
            .first()
        )
        if not asset:
            raise ValueError("NOT_FOUND")
        if not asset.is_public:
            raise ValueError("NOT_PUBLIC")
        if asset.user_id == user_id:
            raise ValueError("CANNOT_RATE_OWN")

        if not (1 <= note <= 5):
            raise ValueError("INVALID_NOTE")

        # Upsert de la note
        existing = (
            self.db.query(AssetRating)
            .filter(
                AssetRating.asset_id == asset_id,
                AssetRating.user_id == user_id,
            )
            .first()
        )
        if existing:
            existing.note = note
            existing.commentaire = commentaire
        else:
            new_rating = AssetRating(
                asset_id=asset_id,
                user_id=user_id,
                note=note,
                commentaire=commentaire,
            )
            self.db.add(new_rating)

        self.db.commit()

        # Recalculer la note moyenne
        await self.recalculer_note_moyenne(asset_id)

        return {
            "asset_id": asset_id,
            "note": note,
            "commentaire": commentaire,
            "message": "Note enregistree avec succes",
        }

    # ─────────────────────────────────────────────────────────────
    # Recalculer la note moyenne
    # ─────────────────────────────────────────────────────────────
    async def recalculer_note_moyenne(self, asset_id: int):
        """Calcule AVG/COUNT depuis AssetRating et met a jour PedagogicalAsset."""
        result = (
            self.db.query(
                func.avg(AssetRating.note).label("avg_note"),
                func.count(AssetRating.id).label("count_notes"),
            )
            .filter(AssetRating.asset_id == asset_id)
            .first()
        )

        avg_note = float(result.avg_note) if result.avg_note is not None else None
        count_notes = result.count_notes or 0

        self.db.query(PedagogicalAsset).filter(
            PedagogicalAsset.id == asset_id
        ).update({
            "note_moyenne": avg_note,
            "nb_notes": count_notes,
        })
        self.db.commit()

    # ─────────────────────────────────────────────────────────────
    # Obtenir la note d'un utilisateur
    # ─────────────────────────────────────────────────────────────
    async def obtenir_ma_note(self, asset_id: int, user_id):
        """Retourne la note de l'utilisateur pour un asset, ou None."""
        rating = (
            self.db.query(AssetRating)
            .filter(
                AssetRating.asset_id == asset_id,
                AssetRating.user_id == user_id,
            )
            .first()
        )
        if not rating:
            return None
        return rating.serialize()
