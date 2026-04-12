"""
services/library_stats_service.py
==================================
Service pour les statistiques globales de la bibliotheque.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import func

from app.modules.library.models import PedagogicalAsset

from .base import LibraryBaseService

logger = logging.getLogger(__name__)


class LibraryStatsService(LibraryBaseService):
    # ─────────────────────────────────────────────────────────────
    # Statistiques globales
    # ─────────────────────────────────────────────────────────────
    def get_stats_globales(self) -> dict:
        """Retourne les statistiques globales de la bibliotheque."""
        # Total assets
        total_assets = (
            self.db.query(func.count(PedagogicalAsset.id))
            .filter(PedagogicalAsset.is_deleted.isnot(True))
            .scalar() or 0
        )

        # Public assets
        public_assets = (
            self.db.query(func.count(PedagogicalAsset.id))
            .filter(
                PedagogicalAsset.is_public == True,
                PedagogicalAsset.is_deleted.isnot(True),
            )
            .scalar() or 0
        )

        # Par type
        by_type_rows = (
            self.db.query(
                PedagogicalAsset.asset_type,
                func.count(PedagogicalAsset.id),
            )
            .filter(PedagogicalAsset.is_deleted.isnot(True))
            .group_by(PedagogicalAsset.asset_type)
            .all()
        )
        by_type = {row[0]: row[1] for row in by_type_rows}

        # Generes les 7 derniers jours
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        generated_7j = (
            self.db.query(func.count(PedagogicalAsset.id))
            .filter(
                PedagogicalAsset.is_deleted.isnot(True),
                PedagogicalAsset.created_at >= seven_days_ago,
            )
            .scalar() or 0
        )

        # Estimation du stockage
        total_storage = (
            self.db.query(func.coalesce(func.sum(PedagogicalAsset.file_size_bytes), 0))
            .filter(
                PedagogicalAsset.is_deleted.isnot(True),
                PedagogicalAsset.file_size_bytes.isnot(None),
            )
            .scalar() or 0
        )

        # Taux de partage
        share_rate = (public_assets / total_assets * 100) if total_assets > 0 else 0.0

        return {
            "total_assets": total_assets,
            "public_assets": public_assets,
            "by_type": by_type,
            "generated_7j": generated_7j,
            "total_storage_bytes": total_storage,
            "share_rate": round(share_rate, 2),
        }

    # ─────────────────────────────────────────────────────────────
    # Top assets
    # ─────────────────────────────────────────────────────────────
    def get_top_assets(self, limit: int = 10) -> list:
        """Retourne les meilleurs assets publics ordonnes par note_moyenne * nb_copies."""
        assets = (
            self.db.query(PedagogicalAsset)
            .filter(
                PedagogicalAsset.is_public == True,
                PedagogicalAsset.is_deleted.isnot(True),
                PedagogicalAsset.note_moyenne.isnot(None),
            )
            .order_by(
                (
                    func.coalesce(PedagogicalAsset.note_moyenne, 0)
                    * func.coalesce(PedagogicalAsset.nb_copies, 1)
                ).desc()
            )
            .limit(limit)
            .all()
        )
        return [
            a.serialize_list_item(is_owner=False, mask_author=True) for a in assets
        ]

    # ─────────────────────────────────────────────────────────────
    # Compteur d'assets utilisateur
    # ─────────────────────────────────────────────────────────────
    def get_user_asset_count(self, user_id) -> int:
        """Retourne le nombre d'assets d'un utilisateur."""
        return (
            self.db.query(func.count(PedagogicalAsset.id))
            .filter(
                PedagogicalAsset.user_id == user_id,
                PedagogicalAsset.is_deleted.isnot(True),
            )
            .scalar() or 0
        )
