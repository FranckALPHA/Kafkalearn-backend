"""
services/base.py
================
Classe de base pour les services du module skills.
"""
import re
import logging
from redis import Redis
from sqlalchemy.orm import Session
from app.core.config import REDIS_URL

logger = logging.getLogger(__name__)


class SkillsBaseService:
    """Classe mère avec utilitaires communs pour les services skills."""

    def __init__(self, db: Session, redis: Redis = None):
        self.db = db
        self.redis = redis or Redis.from_url(REDIS_URL, decode_responses=True, db=2)

    def _normaliser_texte(self, texte: str) -> str:
        """Nettoie et normalise le texte."""
        texte = re.sub(r"[^\w\s\u00C0-\u024F]", " ", texte.lower())
        texte = re.sub(r"\s+", " ", texte).strip()
        return texte
