"""
jobs/crons.py
=============
Tâches planifiées Celery Beat pour le module search.
"""
import logging
from datetime import datetime, timedelta

from app.modules.search.jobs.celery_placeholder import celery_app
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="search.crons.cleanup_old_search_logs", queue="cron")
def cleanup_old_search_logs(days_to_keep: int = 365):
    """
    Supprime les search_logs anciens (RGPD + performance).
    Conserve les logs avec feedback pour l'entraînement des modèles.
    Exécuté quotidiennement via Celery Beat.
    """
    db = SessionLocal()
    try:
        from app.modules.search.models import SearchLog, SearchChunkReturned

        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        batch_size = 1000
        deleted = 0

        while True:
            ids_to_delete = [
                row[0]
                for row in db.query(SearchLog.id)
                .filter(
                    SearchLog.created_at < cutoff,
                    SearchLog.feedback_rating.is_(None),
                )
                .limit(batch_size)
                .all()
            ]

            if not ids_to_delete:
                break

            # Suppression en cascade des chunks_retournes
            db.query(SearchChunkReturned).filter(
                SearchChunkReturned.search_log_id.in_(ids_to_delete)
            ).delete(synchronize_session=False)

            # Suppression des logs
            db.query(SearchLog).filter(
                SearchLog.id.in_(ids_to_delete)
            ).delete(synchronize_session=False)

            db.commit()
            deleted += len(ids_to_delete)
            logger.info(f"Cleanup search_logs: {deleted} supprimés à ce jour")

        logger.info(f"Cleanup terminé: {deleted} search_logs anciens supprimés")
        return {"deleted_count": deleted}

    except Exception as e:
        logger.error(f"Erreur cleanup search_logs: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="search.crons.refresh_filter_cache", queue="cron")
def refresh_filter_cache():
    """
    Rafraîchit le cache des filtres UI (matières, niveaux, séries...).
    Exécuté toutes les 2 heures pour refléter les nouveaux documents indexés.
    """
    try:
        from app.modules.search.services.filter_cache_service import FilterCacheService
        from app.core.database import SessionLocal
        from app.core.config import REDIS_URL
        from redis import Redis

        db = SessionLocal()
        redis = Redis.from_url(REDIS_URL, decode_responses=True, db=1)

        FilterCacheService(db, redis).invalider_et_reconstruire()
        db.close()
        logger.info("Filter cache refreshed successfully")
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Erreur refresh filter cache: {e}")
        raise refresh_filter_cache.retry(exc=e, countdown=300)


@celery_app.task(name="search.crons.refresh_suggestions_cache", queue="cron")
def refresh_suggestions_cache():
    """
    Rafraîchit les suggestions de recherche pour les utilisateurs actifs.
    Exécuté quotidiennement pour les utilisateurs avec TTL expiré.
    """
    db = SessionLocal()
    try:
        from app.modules.search.models import SearchSuggestionCache
        from sqlalchemy import func

        # Supprimer les suggestions expirées
        expired = (
            db.query(SearchSuggestionCache)
            .filter(SearchSuggestionCache.expires_at < datetime.utcnow())
            .delete(synchronize_session=False)
        )

        db.commit()
        logger.info(f"Suggestions cache cleanup: {expired} expired entries removed")
        return {"cleaned": expired}

    except Exception as e:
        logger.error(f"Erreur refresh suggestions cache: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="search.crons.compute_daily_stats", queue="cron")
def compute_daily_stats():
    """
    Calcule les statistiques de la veille pour le dashboard admin.
    Exécuté chaque jour à minuit.
    """
    db = SessionLocal()
    try:
        from app.modules.search.models import SearchLog
        from sqlalchemy import func, desc

        yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        today = yesterday + timedelta(days=1)

        # Stats de la veille
        stats = (
            db.query(
                func.count(SearchLog.id).label("total"),
                func.count(SearchLog.id).filter(SearchLog.reponse_ia_generee == True).label("with_ia"),  # noqa
                func.avg(SearchLog.latence_totale_ms).label("avg_latency"),
                func.avg(SearchLog.nb_chunks_retournes).label("avg_chunks"),
                func.count(SearchLog.id).filter(SearchLog.feedback_rating >= 4).label("positive_feedback"),
                func.count(SearchLog.id).filter(SearchLog.feedback_rating <= 2).label("negative_feedback"),
            )
            .filter(SearchLog.created_at >= yesterday, SearchLog.created_at < today)
            .first()
        )

        if stats:
            logger.info(
                f"Daily stats for {yesterday.date()}: "
                f"total={stats.total}, ia={stats.with_ia}, "
                f"avg_latency={stats.avg_latency:.0f}ms, "
                f"avg_chunks={stats.avg_chunks:.1f}"
            )

        return {
            "date": yesterday.date().isoformat(),
            "total_searches": stats.total if stats else 0,
            "searches_with_ia": stats.with_ia if stats else 0,
            "avg_latency_ms": round(float(stats.avg_latency), 1) if stats and stats.avg_latency else 0,
            "avg_chunks_returned": round(float(stats.avg_chunks), 1) if stats and stats.avg_chunks else 0,
        }

    except Exception as e:
        logger.error(f"Erreur compute_daily_stats: {e}")
        raise
    finally:
        db.close()


@celery_app.task(name="search.crons.detect_anomalies", queue="cron")
def detect_search_anomalies():
    """
    Détecte les anomalies de recherche (erreurs Vespa/LLM en masse).
    Exécuté toutes les 30 minutes.
    """
    db = SessionLocal()
    try:
        from app.modules.search.models import SearchLog
        from datetime import datetime, timedelta

        window = timedelta(minutes=30)
        cutoff = datetime.utcnow() - window

        # Compter les erreurs récentes
        vespa_errors = (
            db.query(SearchLog)
            .filter(
                SearchLog.created_at >= cutoff,
                SearchLog.erreur_ia == "VESPA_ERROR",
            )
            .count()
        )

        llm_errors = (
            db.query(SearchLog)
            .filter(
                SearchLog.created_at >= cutoff,
                SearchLog.erreur_ia == "LLM_ERROR",
            )
            .count()
        )

        # Seuil d'alerte
        if vespa_errors > 50:
            logger.warning(
                f"ALERT: {vespa_errors} Vespa errors in the last 30 minutes!"
            )
            # Notification admin
            _send_admin_alert(
                "Alerte search — erreurs Vespa",
                f"{vespa_errors} erreurs Vespa détectées dans les 30 dernières minutes",
                "vespa",
            )

        if llm_errors > 20:
            logger.warning(
                f"ALERT: {llm_errors} LLM errors in the last 30 minutes!"
            )
            # Notification admin
            _send_admin_alert(
                "Alerte search — erreurs LLM",
                f"{llm_errors} erreurs LLM détectées dans les 30 dernières minutes",
                "llm",
            )

        return {
            "window_minutes": 30,
            "vespa_errors": vespa_errors,
            "llm_errors": llm_errors,
            "alert": vespa_errors > 50 or llm_errors > 20,
        }

    except Exception as e:
        logger.error(f"Erreur detect_search_anomalies: {e}")
        raise
    finally:
        db.close()


def _send_admin_alert(title: str, body: str, module: str):
    """Envoie une notification d'alerte aux admins."""
    try:
        from app.modules.notifications.services.notification_service import NotificationService
        from app.core.database import SessionLocal
        from app.modules.users.models import User
        ndb = SessionLocal()
        admins = ndb.query(User).filter(User.role.in_(("superadmin", "admin"))).all()
        for admin in admins:
            NotificationService(ndb).send_to_user(
                user_id=admin.id,
                title=title,
                body=body,
                data={"type": "search_alert", "module": module},
            )
        ndb.close()
    except Exception:
        pass
