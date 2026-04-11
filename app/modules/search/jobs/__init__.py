"""
jobs/__init__.py
================
Jobs du module search.
"""
from .tasks import (
    enrich_profile_after_search_task,
    classify_intent_background_task,
    cleanup_old_search_logs,
)
from .crons import (
    cleanup_old_search_logs as cleanup_old_search_logs_cron,
    refresh_filter_cache,
    refresh_suggestions_cache,
    compute_daily_stats,
    detect_search_anomalies,
)

__all__ = [
    "enrich_profile_after_search_task",
    "classify_intent_background_task",
    "cleanup_old_search_logs",
    "cleanup_old_search_logs_cron",
    "refresh_filter_cache",
    "refresh_suggestions_cache",
    "compute_daily_stats",
    "detect_search_anomalies",
]
