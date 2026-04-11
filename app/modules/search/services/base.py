"""
services/base.py
================
Classe de base pour les services du module search.
"""
import re
import logging
from redis import Redis
from sqlalchemy.orm import Session
from app.core.config import REDIS_URL
from app.modules.search.utils.constants import STOPWORDS_FR

logger = logging.getLogger(__name__)


class SearchBaseService:
    """Classe mère avec utilitaires communs."""

    def __init__(self, db: Session, redis: Redis = None):
        self.db = db
        self.redis = redis or Redis.from_url(REDIS_URL, decode_responses=True, db=1)

    def _normaliser_texte(self, texte: str) -> str:
        """Nettoie et normalise la requête."""
        texte = re.sub(r"[^\w\s\u00C0-\u024F]", " ", texte.lower())
        texte = re.sub(r"\s+", " ", texte).strip()
        mots = [m for m in texte.split() if m not in STOPWORDS_FR]
        return " ".join(mots)
