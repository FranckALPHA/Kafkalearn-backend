"""
filter_cache_service.py
=======================
Gestion du cache des filtres (matières, niveaux, séries, régions, etc.).
"""
import json
import logging
from typing import Any, Dict, List

from redis import Redis
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.modules.epreuves.services.base import EpreuvesBaseService
from app.modules.epreuves.models import Document
from app.modules.epreuves.utils.meilisearch_client import MeiliClient

logger = logging.getLogger(__name__)

CACHE_KEY = "epreuves:filtres:v1"
CACHE_TTL = 600  # 10 minutes


class FilterCacheService(EpreuvesBaseService):

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)
        self.meili = MeiliClient(self.redis)

    # ── Lecture ───────────────────────────────────────────────────

    def get_filters(self) -> Dict[str, List[str]]:
        """Récupère les filtres depuis le cache Redis, MeiliSearch, ou la DB."""
        # 1. Try Redis cache
        cached = self.redis.get(CACHE_KEY)
        if cached:
            return json.loads(cached)

        # 2. Try MeiliSearch
        if self.meili.available:
            try:
                filters = self.meili.get_available_filters()
                self.redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(filters))
                return filters
            except Exception as e:
                logger.warning(f"MeiliSearch get_available_filters failed: {e}")

        # 3. Build from DB
        filters = self._build_filters_from_db()
        self.redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(filters))
        return filters

    # ── Reconstruction ────────────────────────────────────────────

    def invalider_et_reconstruire(self) -> Dict[str, List[str]]:
        """Invalide le cache et reconstruit les filtres depuis la DB."""
        self.redis.delete(CACHE_KEY)
        if self.meili.available:
            try:
                self.meili.invalidate_filters_cache()
            except Exception as e:
                logger.debug(f"Meili invalidate failed: {e}")

        filters = self._build_filters_from_db()
        self.redis.setex(CACHE_KEY, CACHE_TTL, json.dumps(filters))
        return filters

    # ── Private helpers ───────────────────────────────────────────

    def _build_filters_from_db(self) -> Dict[str, Any]:
        """Construit les valeurs de filtres depuis la table Document."""
        from app.modules.epreuves.utils.constants import (
            MATIERES, NIVEAUX, SERIES, REGIONS,
        )

        # Query distinct values from DB
        matiere_rows = (
            self.db.query(Document.matiere)
            .distinct()
            .all()
        )
        matieres_db = sorted(set(r.matiere for r in matiere_rows if r.matiere))

        niveau_rows = (
            self.db.query(Document.niveau)
            .distinct()
            .all()
        )
        niveaux_db = sorted(set(r.niveau for r in niveau_rows if r.niveau))

        serie_rows = (
            self.db.query(Document.serie)
            .filter(Document.serie.isnot(None))
            .distinct()
            .all()
        )
        series_db = sorted(set(r.serie for r in serie_rows if r.serie))

        region_rows = (
            self.db.query(Document.region)
            .filter(Document.region.isnot(None))
            .distinct()
            .all()
        )
        regions_db = sorted(set(r.region for r in region_rows if r.region))

        # Get distinct years
        annee_rows = (
            self.db.query(Document.annee)
            .distinct()
            .order_by(Document.annee.desc())
            .all()
        )
        annees = sorted([r.annee for r in annee_rows if r.annee], reverse=True)

        # Merge DB values with constants (constants as fallback)
        filters = {
            "matieres": matieres_db if matieres_db else MATIERES,
            "niveaux": niveaux_db if niveaux_db else NIVEAUX,
            "series": series_db if series_db else SERIES,
            "annees": annees if annees else list(range(2026, 2018, -1)),
            "regions": regions_db if regions_db else REGIONS,
            "types": ["epreuve", "lecon"],
            "langues": ["fr", "en"],
        }

        return filters
