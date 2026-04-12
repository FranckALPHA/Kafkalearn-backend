from .tasks import (
    increment_asset_stat_task,
    recalculate_avg_ratings_task,
    cleanup_failed_assets_task,
    calculate_admin_stats_task,
    cleanup_orphan_copies_task,
)
from .celery_app import celery_app

__all__ = [
    "celery_app",
    "increment_asset_stat_task",
    "recalculate_avg_ratings_task",
    "cleanup_failed_assets_task",
    "calculate_admin_stats_task",
    "cleanup_orphan_copies_task",
]
