"""
jobs/__init__.py
================
Jobs du module skills.
"""
from .tasks import (
    generate_fiche_pdf_task,
    enrich_profile_after_skill_task,
    cleanup_old_sessions,
)
from .crons import (
    cleanup_old_sessions_cron,
    compute_weekly_stats,
    detect_skill_errors,
)

__all__ = [
    "generate_fiche_pdf_task",
    "enrich_profile_after_skill_task",
    "cleanup_old_sessions",
    "cleanup_old_sessions_cron",
    "compute_weekly_stats",
    "detect_skill_errors",
]
