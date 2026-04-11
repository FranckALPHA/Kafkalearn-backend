"""
jobs/__init__.py
================
Jobs du module epreuves.
"""
from .tasks import (
    run_ingestion,
    log_document_view_task,
    log_download_task,
    increment_document_stat_task,
    update_document_stats_task,
    recalculate_trending_task,
    cleanup_old_views_task,
    alert_missing_files_task,
)
from .celery_app import celery_app

__all__ = [
    "celery_app",
    "run_ingestion",
    "log_document_view_task",
    "log_download_task",
    "increment_document_stat_task",
    "update_document_stats_task",
    "recalculate_trending_task",
    "cleanup_old_views_task",
    "alert_missing_files_task",
]
