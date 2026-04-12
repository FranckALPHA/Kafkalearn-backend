import logging
from datetime import datetime, timedelta

from app.modules.library.jobs.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_db():
    """Helper to get a SQLAlchemy session."""
    from app.core.database import SessionLocal
    return SessionLocal()


@celery_app.task(bind=True, max_retries=3)
def increment_asset_stat_task(self, asset_id, stat_field, value=1):
    """Atomically increment a stat field (nb_vues, nb_telechargements) on a PedagogicalAsset."""
    db = _get_db()
    try:
        from app.modules.library.models import PedagogicalAsset
        db.query(PedagogicalAsset).filter(
            PedagogicalAsset.id == asset_id
        ).update({
            stat_field: getattr(PedagogicalAsset, stat_field) + value,
        })
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to increment %s on asset %s: %s", stat_field, asset_id, exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def recalculate_avg_ratings_task(self):
    """Recalculate note_moyenne for all assets that have ratings."""
    db = _get_db()
    try:
        from sqlalchemy import func
        from app.modules.library.models import PedagogicalAsset, AssetRating

        assets_with_ratings = (
            db.query(AssetRating.asset_id)
            .group_by(AssetRating.asset_id)
            .all()
        )
        asset_ids = [row[0] for row in assets_with_ratings]

        for asset_id in asset_ids:
            result = (
                db.query(
                    func.avg(AssetRating.note).label("avg_note"),
                    func.count(AssetRating.id).label("count_notes"),
                )
                .filter(AssetRating.asset_id == asset_id)
                .first()
            )
            avg_note = float(result.avg_note) if result.avg_note is not None else None
            count_notes = result.count_notes or 0

            db.query(PedagogicalAsset).filter(
                PedagogicalAsset.id == asset_id
            ).update({
                "note_moyenne": avg_note,
                "nb_notes": count_notes,
            })

        db.commit()
        logger.info("Recalculated average ratings for %d assets", len(asset_ids))
    except Exception as exc:
        db.rollback()
        logger.error("Failed to recalculate ratings: %s", exc)
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def cleanup_failed_assets_task(self):
    """Soft-delete assets in 'failed' status older than 24 hours."""
    db = _get_db()
    try:
        from app.modules.library.models import PedagogicalAsset

        cutoff = datetime.utcnow() - timedelta(hours=24)
        result = (
            db.query(PedagogicalAsset)
            .filter(
                PedagogicalAsset.generation_status == "failed",
                PedagogicalAsset.created_at < cutoff,
                PedagogicalAsset.is_deleted.isnot(True),
            )
            .update({"is_deleted": True}, synchronize_session="fetch")
        )
        db.commit()
        logger.info("Soft-deleted %d failed assets", result)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to cleanup failed assets: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def calculate_admin_stats_task(self):
    """Calculate global library stats and cache in Redis for 24h."""
    db = _get_db()
    try:
        from redis import Redis
        from app.core.config import REDIS_URL
        from app.modules.library.services.library_stats_service import LibraryStatsService

        stats_service = LibraryStatsService(db=db)
        stats = stats_service.get_stats_globales()
        top_assets = stats_service.get_top_assets(limit=10)

        cache_data = {**stats, "top_assets": top_assets}

        redis_client = Redis.from_url(REDIS_URL, decode_responses=True, db=7)
        redis_client.setex(
            "library:admin_stats",
            86400,  # 24 hours
            str(cache_data),
        )
        logger.info("Admin stats calculated and cached")
    except Exception as exc:
        logger.error("Failed to calculate admin stats: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def cleanup_orphan_copies_task(self):
    """Remove AssetCopy entries where copy_asset_id no longer exists."""
    db = _get_db()
    try:
        from sqlalchemy import exists
        from app.modules.library.models import AssetCopy, PedagogicalAsset

        orphan_copies = (
            db.query(AssetCopy)
            .filter(
                ~exists().where(PedagogicalAsset.id == AssetCopy.copy_asset_id)
            )
            .all()
        )
        count = len(orphan_copies)
        for copy_record in orphan_copies:
            db.delete(copy_record)

        db.commit()
        logger.info("Cleaned up %d orphan copies", count)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to cleanup orphan copies: %s", exc)
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()
