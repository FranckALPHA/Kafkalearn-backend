"""
recommendation_engine.py
========================
Moteur de recommandation : lacunes, populaires, similaires, mix.
"""
import logging
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.modules.epreuves.services.base import EpreuvesBaseService
from app.modules.epreuves.models import Document, DocumentView

logger = logging.getLogger(__name__)


class RecommendationEngine(EpreuvesBaseService):

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    # ── Recommandation par lacunes ────────────────────────────────

    def recommander_par_lacunes(
        self,
        user_id: Any,
        matiere: str,
        notions: List[str],
        limit: int = 10,
    ) -> List[dict]:
        """Recommande des documents ciblant les notions où l'utilisateur a des lacunes."""
        if not notions:
            return []

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

        docs = q.all()
        results = [d.serialize_list_item() for d in docs]

        # If not enough by notion_principale, broaden to keywords
        if len(results) < limit:
            remaining = limit - len(results)
            q2 = (
                self.db.query(Document)
                .filter(
                    Document.is_validated == True,  # noqa: E712
                    Document.matiere == matiere,
                    Document.mots_cles.op("@>")(notions[:1]),  # JSONB contains
                )
                .order_by(desc(Document.nb_vues))
                .limit(remaining)
            )
            for d in q2.all():
                item = d.serialize_list_item()
                if item["id"] not in [r["id"] for r in results]:
                    results.append(item)

        return results[:limit]

    # ── Recommandation populaires ─────────────────────────────────

    def recommander_populaires(
        self,
        matiere: Optional[str] = None,
        niveau: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Documents les plus populaires (vues), filtrables par matière/niveau."""
        q = (
            self.db.query(Document)
            .filter(
                Document.is_validated == True,  # noqa: E712
            )
        )
        if matiere:
            q = q.filter(Document.matiere == matiere)
        if niveau:
            q = q.filter(Document.niveau == niveau)

        q = q.order_by(desc(Document.nb_vues)).limit(limit)
        docs = q.all()
        return [d.serialize_list_item() for d in docs]

    # ── Recommandation similaires ─────────────────────────────────

    def recommander_similaires(
        self,
        doc_id: int,
        limit: int = 10,
    ) -> List[dict]:
        """Documents similaires par matière et notion principale."""
        source = (
            self.db.query(Document)
            .filter(Document.id == doc_id)
            .first()
        )
        if not source:
            return []

        q = (
            self.db.query(Document)
            .filter(
                Document.is_validated == True,  # noqa: E712
                Document.id != doc_id,
                Document.matiere == source.matiere,
            )
        )

        # Prefer same notion
        if source.notion_principale:
            q = q.filter(Document.notion_principale == source.notion_principale)

        # Also match same niveau, serie, annee for additional relevance
        conditions = []
        if source.niveau:
            conditions.append(Document.niveau == source.niveau)
        if source.serie:
            conditions.append(Document.serie == source.serie)

        q = q.order_by(desc(Document.nb_vues)).limit(limit)
        docs = q.all()

        # If not enough with notion filter, broaden to just matiere
        if len(docs) < limit:
            remaining = limit - len(docs)
            seen_ids = {d.id for d in docs}
            q2 = (
                self.db.query(Document)
                .filter(
                    Document.is_validated == True,  # noqa: E712
                    Document.id != doc_id,
                    Document.matiere == source.matiere,
                    ~Document.id.in_(seen_ids) if seen_ids else True,
                )
                .order_by(desc(Document.nb_vues))
                .limit(remaining)
            )
            docs.extend(q2.all())

        return [d.serialize_list_item() for d in docs]

    # ── Mix : lacunes + populaires + similaires ───────────────────

    def recommander_mix(
        self,
        user_id: Any,
        limit: int = 10,
    ) -> List[dict]:
        """Combine recommandations par lacunes (graphe), populaires et similaires."""
        from app.modules.memory.services.concept_graph_service import ConceptGraphService

        graph_svc = ConceptGraphService(self.db)
        lacunes = graph_svc.get_concepts_lacunes(str(user_id))
        stats = graph_svc.get_statistiques_personnelles(str(user_id))

        lacunes_docs = []
        populaires_docs = []
        similaires_docs = []

        # 1. Lacunes-based (40% of limit) — depuis le graphe cognitif
        if lacunes:
            lacune_limit = max(1, int(limit * 0.4))
            for matiere, notions in lacunes.items():
                if notions:
                    lacunes_docs = self.recommander_par_lacunes(
                        user_id=user_id,
                        matiere=matiere,
                        notions=notions,
                        limit=lacune_limit,
                    )
                    if lacunes_docs:
                        break

        # 2. Populaires (30% of limit) — matière principale du graphe
        pop_limit = max(1, int(limit * 0.3))
        matiere_principale = stats.get("matiere_principale")
        if matiere_principale:
            populaires_docs = self.recommander_populaires(
                matiere=matiere_principale,
                limit=pop_limit,
            )
        else:
            populaires_docs = self.recommander_populaires(limit=pop_limit)

        # 3. Similar to recently viewed (30% of limit)
        sim_limit = max(1, limit - len(lacunes_docs) - len(populaires_docs))
        if sim_limit > 0:
            # Find most recent viewed document for this user
            recent_view = (
                self.db.query(DocumentView)
                .filter(DocumentView.user_id == user_id)
                .order_by(desc(DocumentView.created_at))
                .first()
            )
            if recent_view:
                similaires_docs = self.recommander_similaires(
                    doc_id=recent_view.document_id,
                    limit=sim_limit,
                )

        # Merge and deduplicate
        seen_ids = set()
        results = []
        for doc_list in [lacunes_docs, populaires_docs, similaires_docs]:
            for item in doc_list:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    results.append(item)
                    if len(results) >= limit:
                        return results

        return results[:limit]
