"""
jobs/crons.py
=============
Tâches planifiées Celery Beat pour le module skills.
"""
import logging
from datetime import datetime, timedelta

from app.modules.skills.jobs.celery_app import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="skills.crons.cleanup_old_sessions", queue="cron")
def cleanup_old_sessions_cron():
    """Nettoyage périodique des sessions anciennes."""
    from app.modules.skills.jobs.tasks import cleanup_old_sessions
    return cleanup_old_sessions()


@celery_app.task(name="skills.crons.compute_weekly_stats", queue="cron")
def compute_weekly_stats():
    """Calcule les statistiques hebdomadaires des skills."""
    db = SessionLocal()
    try:
        from app.modules.skills.models import SkillUsageLog, QuizSession
        from sqlalchemy import func

        week_ago = datetime.utcnow() - timedelta(days=7)

        # Skills les plus utilisés
        top_skills = (
            db.query(
                SkillUsageLog.skill_type,
                func.count(SkillUsageLog.id).label("count"),
            )
            .filter(SkillUsageLog.created_at >= week_ago)
            .group_by(SkillUsageLog.skill_type)
            .order_by(func.count(SkillUsageLog.id).desc())
            .limit(5)
            .all()
        )

        # Quiz stats
        avg_quiz_score = (
            db.query(func.avg(QuizSession.score_percent))
            .filter(QuizSession.started_at >= week_ago)
            .scalar()
        ) or 0

        logger.info(
            f"Weekly stats: top_skills={[{'skill': s.skill_type, 'count': s.count} for s in top_skills]}, "
            f"avg_quiz_score={round(float(avg_quiz_score), 1)}"
        )

        return {
            "top_skills": [{"skill": s.skill_type, "count": s.count} for s in top_skills],
            "avg_quiz_score": round(float(avg_quiz_score), 1),
        }

    except Exception as e:
        logger.error(f"Erreur compute_weekly_stats: {e}")
        raise
    finally:
        db.close()


@celery_app.task(name="skills.crons.detect_skill_errors", queue="cron")
def detect_skill_errors():
    """Détecte les erreurs de skills en masse (anomalies)."""
    db = SessionLocal()
    try:
        from app.modules.skills.models import SkillUsageLog

        hour_ago = datetime.utcnow() - timedelta(hours=1)

        error_count = (
            db.query(SkillUsageLog)
            .filter(
                SkillUsageLog.created_at >= hour_ago,
                SkillUsageLog.succes == False,
                SkillUsageLog.erreur_code.isnot(None),
            )
            .count()
        )

        if error_count > 20:
            logger.warning(f"ALERT: {error_count} skill errors in the last hour!")
            # TODO: Envoyer notification admin

        return {"error_count_1h": error_count, "alert": error_count > 20}

    except Exception as e:
        logger.error(f"Erreur detect_skill_errors: {e}")
        raise
    finally:
        db.close()
