"""
modules/core/infra/meili_client.py
==================================
Client MeiliSearch — wrapper centralisé.
"""
import logging
from typing import Optional, List, Dict, Any

import meilisearch

from app.modules.core.config import settings

logger = logging.getLogger(__name__)


class MeiliClient:
    """Client MeiliSearch centralisé."""

    def __init__(self):
        try:
            self.client = meilisearch.Client(settings.MEILI_URL, settings.MEILI_MASTER_KEY)
            self.available = True
        except Exception as e:
            logger.warning(f"MeiliSearch unavailable: {e}")
            self.available = False

    def get_index(self, index_name: str = None):
        idx = index_name or settings.MEILI_INDEX
        if self.available:
            return self.client.index(idx)
        return None

    def index_document(self, doc_data: Dict[str, Any], index_name: str = None):
        idx = self.get_index(index_name)
        if idx:
            try:
                idx.add_documents([doc_data], primary_key="id")
            except Exception as e:
                logger.error(f"MeiliSearch index error: {e}")

    def delete_document(self, doc_id: str, index_name: str = None):
        idx = self.get_index(index_name)
        if idx:
            try:
                idx.delete_document(doc_id)
            except Exception as e:
                logger.error(f"MeiliSearch delete error: {e}")

    def search(self, query: str, index_name: str = None, **kwargs):
        idx = self.get_index(index_name)
        if idx:
            try:
                return idx.search(query, kwargs)
            except Exception as e:
                logger.error(f"MeiliSearch search error: {e}")
        return {"hits": [], "totalHits": 0}
