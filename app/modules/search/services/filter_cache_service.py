"""
services/filter_cache_service.py
================================
Cache des filtres UI (matières, niveaux, séries, années).
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from redis import Redis

from app.modules.search.services.base import SearchBaseService
from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)

CACHE_KEY = "search:filters:all"
CACHE_TTL_SECONDS = 7200  # 2 heures


class FilterCacheService(SearchBaseService):
    """
    Gestion du cache des filtres UI.
    Les filtres sont calculés depuis la BDD et cachés dans Redis.
    """

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)
        if not redis:
            self.redis = Redis.from_url(REDIS_URL, decode_responses=True, db=1)

    def get_filters(self) -> Dict[str, Any]:
        """
        Récupère les filtres depuis le cache Redis.
        Si absent ou expiré, reconstruit depuis la BDD.
        """
        cached = self.redis.get(CACHE_KEY)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                logger.warning("Invalid filter cache, rebuilding...")

        # Reconstruire depuis la BDD
        filters = self._build_filters_from_db()
        self._cache_filters(filters)
        return filters

    def invalider_et_reconstruire(self) -> Dict[str, Any]:
        """Invalide le cache et reconstruit les filtres."""
        self.redis.delete(CACHE_KEY)
        filters = self._build_filters_from_db()
        self._cache_filters(filters)
        logger.info("Filter cache rebuilt")
        return filters

    def _build_filters_from_db(self) -> Dict[str, Any]:
        """
        Construit les filtres depuis les documents en BDD.
        TODO: Adapter selon le schéma réel des documents (Vespa ou autre).
        Pour l'instant, retourne des valeurs statiques + dynamique si BDD dispo.
        """
        # Valeurs par défaut (à remplacer par requêtes BDD réelles)
        filters = {
            "matieres": self._get_matieres(),
            "niveaux": self._get_niveaux(),
            "series": self._get_series(),
            "annees": self._get_annees(),
            "types_doc": ["epreuve", "lecon", "corrige", "exercice"],
            "updated_at": datetime.utcnow().isoformat(),
        }
        return filters

    def _get_matieres(self) -> List[Dict[str, str]]:
        """Liste des matières disponibles."""
        # TODO: Requêtes BDD réelle
        return [
            {"id": "math", "nom": "Mathématiques", "count": 0},
            {"id": "physique", "nom": "Physique", "count": 0},
            {"id": "svt", "nom": "SVT", "count": 0},
            {"id": "francais", "nom": "Français", "count": 0},
            {"id": "anglais", "nom": "Anglais", "count": 0},
            {"id": "histoire", "nom": "Histoire-Géo", "count": 0},
            {"id": "philo", "nom": "Philosophie", "count": 0},
            {"id": "informatique", "nom": "Informatique", "count": 0},
        ]

    def _get_niveaux(self) -> List[Dict[str, str]]:
        """Liste des niveaux disponibles."""
        return [
            {"id": "6e", "nom": "Sixième"},
            {"id": "5e", "nom": "Cinquième"},
            {"id": "4e", "nom": "Quatrième"},
            {"id": "3e", "nom": "Troisième"},
            {"id": "seconde", "nom": "Seconde"},
            {"id": "premiere", "nom": "Première"},
            {"id": "terminale", "nom": "Terminale"},
        ]

    def _get_series(self) -> List[Dict[str, str]]:
        """Liste des séries pour le secondaire."""
        return [
            {"id": "A", "nom": "Série A (Littéraire)"},
            {"id": "C", "nom": "Série C (Scientifique)"},
            {"id": "D", "nom": "Série D (SVT)"},
            {"id": "E", "nom": "Série E (Maths-Physique)"},
            {"id": "F", "nom": "Série F (Technique)"},
            {"id": "G", "nom": "Série G (Tertiaire)"},
        ]

    def _get_annees(self) -> List[int]:
        """Liste des années disponibles."""
        current_year = datetime.utcnow().year
        return list(range(current_year - 15, current_year + 1))

    def _cache_filters(self, filters: Dict[str, Any]):
        """Stocke les filtres dans Redis avec TTL."""
        self.redis.setex(
            CACHE_KEY,
            CACHE_TTL_SECONDS,
            json.dumps(filters, ensure_ascii=False),
        )

    def get_filter_values(self, filter_name: str) -> List[Any]:
        """Récupère les valeurs d'un filtre spécifique."""
        filters = self.get_filters()
        return filters.get(filter_name, [])

    def invalidate_single_filter(self, filter_name: str):
        """Invalide un filtre spécifique (rebuild complet nécessaire)."""
        self.redis.delete(CACHE_KEY)
        logger.info(f"Filter cache invalidated (change in {filter_name})")
