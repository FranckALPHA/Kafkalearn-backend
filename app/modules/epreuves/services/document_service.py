"""
document_service.py
===================
Service CRUD + liste + trending + recommandations pour les documents.
"""
import logging
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.modules.epreuves.services.base import EpreuvesBaseService
from app.modules.epreuves.models import Document, DocumentView
from app.modules.epreuves.utils.storage import StorageService
from app.modules.epreuves.utils.hash_utils import sha256_bytes
from app.modules.epreuves.utils.meilisearch_client import MeiliClient

logger = logging.getLogger(__name__)


class DocumentService(EpreuvesBaseService):

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)
        self.storage = StorageService()
        self.meili = MeiliClient(self.redis)

    # ── CRUD ──────────────────────────────────────────────────────

    async def ajouter_document(
        self,
        file_data: dict,
        metadata: dict,
        uploaded_by: Any = None,
    ) -> dict:
        """Ajoute un document après vérification de déduplication par hash."""
        file_bytes = file_data.get("content")
        if not file_bytes:
            raise ValueError("file_data must contain 'content' key with bytes")

        content_hash = sha256_bytes(file_bytes)

        # Dedup check
        existing = self.db.query(Document).filter(
            Document.hash_contenu == content_hash
        ).first()
        if existing:
            logger.info(f"Duplicate document detected, hash={content_hash}")
            return {
                "document_id": existing.id,
                "is_duplicate": True,
                "ingest_status": existing.ingest_status,
            }

        # Save file via StorageService
        relative_path = metadata.get(
            "chemin_final",
            f"{metadata.get('matiere', 'autre')}/{content_hash[:8]}_{file_data.get('filename', 'doc')}",
        )
        chemin_final = await self.storage.save_file(
            file_bytes=file_bytes,
            relative_path=relative_path,
            mimetype=file_data.get("mimetype", "application/pdf"),
        )

        doc = Document(
            nom_original=file_data.get("filename", "unknown"),
            nom_affiche=metadata.get("nom_affiche", file_data.get("filename")),
            chemin_final=chemin_final,
            mimetype=file_data.get("mimetype", "application/pdf"),
            poids_octets=len(file_bytes),
            hash_contenu=content_hash,
            matiere=metadata.get("matiere", "Autre"),
            niveau=metadata.get("niveau", "Non spécifié"),
            serie=metadata.get("serie"),
            annee=metadata.get("annee", 2026),
            type_doc=metadata.get("type_doc", "epreuve"),
            sous_type=metadata.get("sous_type"),
            notion_principale=metadata.get("notion_principale"),
            mots_cles=metadata.get("mots_cles", []),
            uploaded_by=uploaded_by,
            is_validated=metadata.get("is_validated", False),
            difficulte_estimee=metadata.get("difficulte_estimee"),
            etablissement=metadata.get("etablissement"),
            region=metadata.get("region"),
            langue=metadata.get("langue", "fr"),
        )
        self.db.add(doc)
        self.db.flush()

        # Queue embed / ingest task via Celery (deferred to avoid circular import)
        try:
            from app.modules.epreuves.jobs.tasks import run_ingestion
            run_ingestion.delay(doc.id)
            doc.ingest_status = "processing"
        except Exception as e:
            logger.warning(f"Could not queue ingestion task: {e}")
            doc.ingest_status = "pending"

        self.db.commit()
        self.db.refresh(doc)

        return {
            "document_id": doc.id,
            "is_duplicate": False,
            "ingest_status": doc.ingest_status,
        }

    async def liste_documents(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort: str = "date_desc",
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """Liste les documents avec filtres, tri et pagination."""
        filters = filters or {}
        query_text = filters.pop("query", None)

        # If there's a text query, try MeiliSearch first
        if query_text and self.meili.available:
            meili_filters = {k: v for k, v in filters.items() if v}
            sort_list = self._translate_sort(sort)
            result = await self.meili.search(
                query=query_text,
                filters=meili_filters,
                sort=sort_list,
                page=page,
                limit=limit,
            )
            return result

        # SQL fallback / no text query
        q = self.db.query(Document)

        # Apply dynamic filters
        for field in [
            "matiere", "niveau", "serie", "region",
            "type_doc", "langue", "annee", "is_validated",
        ]:
            if filters.get(field) is not None:
                q = q.filter(getattr(Document, field) == filters[field])

        # Include non-validated only if explicitly requested
        if not filters.get("include_non_validated"):
            q = q.filter(Document.is_validated == True)  # noqa: E712

        # Sorting
        sort_map = {
            "date_desc": desc(Document.created_at),
            "date_asc": Document.created_at,
            "views_desc": desc(Document.nb_vues),
            "name_asc": Document.nom_original,
            "name_desc": desc(Document.nom_original),
        }
        order_col = sort_map.get(sort, desc(Document.created_at))
        q = q.order_by(order_col)

        total = q.count()
        docs = q.offset((page - 1) * limit).limit(limit).all()

        return {
            "hits": [d.serialize_list_item() for d in docs],
            "total": total,
            "page": page,
            "limit": limit,
            "moteur": "sql",
        }

    async def recuperer_par_id(self, doc_id: int) -> Optional[Document]:
        """Récupère un document par son ID."""
        return (
            self.db.query(Document)
            .filter(Document.id == doc_id)
            .first()
        )

    # ── Trending ──────────────────────────────────────────────────

    async def obtenir_trending(
        self,
        periode_jours: int = 7,
        matiere: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Récupère les documents tendance (les plus consultés)."""
        cache_key = f"epreuves:trending:{periode_jours}j"
        if matiere:
            cache_key += f":{matiere}"

        cached = self.redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        # Fallback: compute from DocumentView
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=periode_jours)
        q = (
            self.db.query(
                Document.id,
                Document.nom_original,
                Document.nom_affiche,
                Document.matiere,
                Document.niveau,
                Document.type_doc,
                Document.nb_vues,
            )
            .join(DocumentView, Document.id == DocumentView.document_id)
            .filter(
                Document.is_validated == True,  # noqa: E712
                DocumentView.created_at >= cutoff,
            )
        )
        if matiere:
            q = q.filter(Document.matiere == matiere)

        q = (
            q.group_by(Document.id)
            .order_by(desc(Document.nb_vues))
            .limit(limit)
        )

        rows = q.all()
        results = [
            {
                "id": r.id,
                "nom_original": r.nom_original,
                "nom_affiche": r.nom_affiche,
                "matiere": r.matiere,
                "niveau": r.niveau,
                "type_doc": r.type_doc,
                "nb_vues": r.nb_vues,
            }
            for r in rows
        ]

        # Cache for 5 minutes
        import json
        self.redis.setex(cache_key, 300, json.dumps(results))
        return results

    # ── Recommendations ───────────────────────────────────────────

    async def recommander_pour_utilisateur(
        self,
        user_id: Any,
        limit: int = 10,
    ) -> List[dict]:
        """Recommande des documents basés sur les lacunes du profil utilisateur."""
        from app.modules.users.models import UserLearningProfile

        profile = (
            self.db.query(UserLearningProfile)
            .filter(UserLearningProfile.user_id == user_id)
            .first()
        )
        if not profile or not profile.lacunes:
            return []

        lacunes = profile.lacunes  # dict: {matiere: [notions]}
        recommended = []

        for matiere, notions in lacunes.items():
            if not notions:
                continue
            q = (
                self.db.query(Document)
                .filter(
                    Document.is_validated == True,  # noqa: E712
                    Document.matiere == matiere,
                    Document.notion_principale.in_(notions),
                )
                .order_by(desc(Document.nb_vues))
                .limit(limit)
            )
            for doc in q.all():
                recommended.append(doc.serialize_list_item())

        # Deduplicate by id and limit
        seen = set()
        unique = []
        for item in recommended:
            if item["id"] not in seen:
                seen.add(item["id"])
                unique.append(item)
                if len(unique) >= limit:
                    break

        return unique

    # ── Stats helpers ─────────────────────────────────────────────

    async def incrementer_stat(
        self,
        doc_id: int,
        stat_field: str,
        value: int = 1,
    ) -> None:
        """Incrémente un compteur statistique sur un document et queue une tâche Celery."""
        doc = self.db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            return

        if hasattr(doc, stat_field):
            setattr(doc, stat_field, getattr(doc, stat_field) + value)
            self.db.commit()

        # Queue Celery task for async processing (e.g. recompute averages)
        try:
            from app.modules.epreuves.jobs.tasks import update_document_stats
            update_document_stats.delay(doc_id, stat_field, value)
        except Exception as e:
            logger.debug(f"Could not queue stat update task: {e}")

    async def existe_par_hash(self, content_hash: str) -> bool:
        """Vérifie si un document avec ce hash existe déjà."""
        return (
            self.db.query(Document)
            .filter(Document.hash_contenu == content_hash)
            .first()
            is not None
        )

    # ── Private helpers ───────────────────────────────────────────

    @staticmethod
    def _translate_sort(sort: str) -> List[str]:
        """Traduit un tri interne en format MeiliSearch."""
        sort_map = {
            "date_desc": ["created_at:desc"],
            "date_asc": ["created_at:asc"],
            "views_desc": ["nb_vues:desc"],
            "name_asc": ["nom_affiche:asc"],
            "name_desc": ["nom_affiche:desc"],
        }
        return sort_map.get(sort, ["created_at:desc"])
