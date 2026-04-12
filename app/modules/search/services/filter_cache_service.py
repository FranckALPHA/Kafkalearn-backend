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
        Requêtes réelles sur la table Documents.
        """
        try:
            from app.modules.epreuves.models import Document
            # Matières avec counts
            matieres_raw = (
                self.db.query(
                    Document.matiere,
                    func.count(Document.id).label("count"),
                )
                .filter(
                    Document.matiere.isnot(None),
                    Document.is_deleted == False,
                    Document.is_validated == True,
                )
                .group_by(Document.matiere)
                .order_by(func.count(Document.id).desc())
                .all()
            )
            matieres = [
                {"id": m[0].lower().replace(" ", "_"), "nom": m[0], "count": m[1]}
                for m in matieres_raw
            ]

            # Niveaux avec counts
            niveaux_raw = (
                self.db.query(
                    Document.niveau,
                    func.count(Document.id).label("count"),
                )
                .filter(
                    Document.niveau.isnot(None),
                    Document.is_deleted == False,
                    Document.is_validated == True,
                )
                .group_by(Document.niveau)
                .order_by(func.count(Document.id).desc())
                .all()
            )
            niveaux = [
                {"id": n[0].lower().replace(" ", "_"), "nom": n[0], "count": n[1]}
                for n in niveaux_raw
            ]

            # Séries avec counts
            series_raw = (
                self.db.query(
                    Document.serie,
                    func.count(Document.id).label("count"),
                )
                .filter(
                    Document.serie.isnot(None),
                    Document.is_deleted == False,
                    Document.is_validated == True,
                )
                .group_by(Document.serie)
                .order_by(func.count(Document.id).desc())
                .all()
            )
            series = [
                {"id": s[0], "nom": f"Série {s[0]}", "count": s[1]}
                for s in series_raw if s[0]
            ]

            # Années avec counts
            annees_raw = (
                self.db.query(
                    Document.annee,
                    func.count(Document.id).label("count"),
                )
                .filter(
                    Document.annee.isnot(None),
                    Document.is_deleted == False,
                    Document.is_validated == True,
                )
                .group_by(Document.annee)
                .order_by(Document.annee.desc())
                .all()
            )
            annees = [a[0] for a in annees_raw if a[0]]

            filters = {
                "matieres": matieres if matieres else self._get_default_matieres(),
                "niveaux": niveaux if niveaux else self._get_default_niveaux(),
                "series": series if series else self._get_default_series(),
                "annees": annees if annees else self._get_default_annees(),
                "types_doc": ["epreuve", "lecon", "corrige", "exercice"],
                "updated_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.warning(f"Fallback to static filters: {e}")
            filters = {
                "matieres": self._get_default_matieres(),
                "niveaux": self._get_default_niveaux(),
                "series": self._get_default_series(),
                "annees": self._get_default_annees(),
                "types_doc": ["epreuve", "lecon", "corrige", "exercice"],
                "updated_at": datetime.utcnow().isoformat(),
            }
        return filters

    def _get_default_matieres(self) -> List[Dict[str, str]]:
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

    def _get_default_niveaux(self) -> List[Dict[str, str]]:
        return [
            {"id": "6e", "nom": "Sixième"},
            {"id": "5e", "nom": "Cinquième"},
            {"id": "4e", "nom": "Quatrième"},
            {"id": "3e", "nom": "Troisième"},
            {"id": "seconde", "nom": "Seconde"},
            {"id": "premiere", "nom": "Première"},
            {"id": "terminale", "nom": "Terminale"},
        ]

    def _get_default_series(self) -> List[Dict[str, str]]:
        return [
            {"id": "A", "nom": "Série A (Littéraire)"},
            {"id": "C", "nom": "Série C (Scientifique)"},
            {"id": "D", "nom": "Série D (SVT)"},
            {"id": "E", "nom": "Série E (Maths-Physique)"},
            {"id": "F", "nom": "Série F (Technique)"},
            {"id": "G", "nom": "Série G (Tertiaire)"},
        ]

    def _get_default_annees(self) -> List[int]:
        current_year = datetime.utcnow().year
        return list(range(current_year - 15, current_year + 1))

    def _get_matieres(self) -> List[Dict[str, str]]:
        """Liste des matières disponibles (alias vers default)."""
        return self._get_default_matieres()

    def _get_niveaux(self) -> List[Dict[str, str]]:
        """Liste des niveaux disponibles (alias vers default)."""
        return self._get_default_niveaux()

    def _get_series(self) -> List[Dict[str, str]]:
        """Liste des séries pour le secondaire (alias vers default)."""
        return self._get_default_series()

    def _get_annees(self) -> List[int]:
        """Liste des années disponibles (alias vers default)."""
        return self._get_default_annees()

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
