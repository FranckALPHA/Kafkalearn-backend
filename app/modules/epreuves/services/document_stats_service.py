"""
document_stats_service.py
=========================
Agrégation et consultation des statistiques de documents.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.modules.epreuves.services.base import EpreuvesBaseService
from app.modules.epreuves.models import Document, DocumentView

logger = logging.getLogger(__name__)


class DocumentStatsService(EpreuvesBaseService):

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    # ── Stats par document ────────────────────────────────────────

    def get_stats_document(self, doc_id: int) -> Optional[dict]:
        """Agrège vues, téléchargements, favoris, score moyen pour un document."""
        doc = (
            self.db.query(Document)
            .filter(Document.id == doc_id)
            .first()
        )
        if not doc:
            return None

        # Aggregate views by source from DocumentView
        view_counts = (
            self.db.query(
                DocumentView.source,
                sa_func.count(DocumentView.id).label("count"),
            )
            .filter(DocumentView.document_id == doc_id)
            .group_by(DocumentView.source)
            .all()
        )
        views_by_source = {row.source: row.count for row in view_counts}

        # Recalculate average score if needed
        avg_score = self._recalculer_score_moyen(doc_id)

        return {
            "document_id": doc_id,
            "nb_vues": doc.nb_vues,
            "nb_telechargements": doc.nb_telechargements,
            "nb_favoris": doc.nb_favoris,
            "nb_tentatives_ia": doc.nb_tentatives_ia,
            "score_moyen_utilisateurs": avg_score or doc.score_moyen_utilisateurs,
            "views_by_source": views_by_source,
            "is_validated": doc.is_validated,
            "is_embedded": doc.is_embedded,
        }

    # ── Top documents ─────────────────────────────────────────────

    def get_top_documents_par_matiere(
        self,
        matiere: str,
        limit: int = 10,
    ) -> List[dict]:
        """Top documents par matière, ordonnés par nb_vues."""
        docs = (
            self.db.query(Document)
            .filter(
                Document.matiere == matiere,
                Document.is_validated == True,  # noqa: E712
            )
            .order_by(Document.nb_vues.desc())
            .limit(limit)
            .all()
        )
        return [d.serialize_list_item() for d in docs]

    # ── Documents récents ─────────────────────────────────────────

    def get_documents_recents(
        self,
        matiere: Optional[str] = None,
        limit: int = 10,
    ) -> List[dict]:
        """Documents validés les plus récents."""
        q = (
            self.db.query(Document)
            .filter(
                Document.is_validated == True,  # noqa: E712
            )
            .order_by(Document.created_at.desc())
        )
        if matiere:
            q = q.filter(Document.matiere == matiere)

        docs = q.limit(limit).all()
        return [d.serialize_list_item() for d in docs]

    # ── Stats globales ────────────────────────────────────────────

    def get_stats_globales(self) -> dict:
        """Statistiques globales : totaux, par matière, par niveau."""
        # Totals
        total_docs = (
            self.db.query(sa_func.count(Document.id))
            .scalar()
        )
        total_validated = (
            self.db.query(sa_func.count(Document.id))
            .filter(Document.is_validated == True)  # noqa: E712
            .scalar()
        )
        total_embedded = (
            self.db.query(sa_func.count(Document.id))
            .filter(Document.is_embedded == True)  # noqa: E712
            .scalar()
        )

        # By matiere
        matiere_rows = (
            self.db.query(
                Document.matiere,
                sa_func.count(Document.id).label("count"),
            )
            .group_by(Document.matiere)
            .all()
        )
        par_matiere = {row.matiere: row.count for row in matiere_rows}

        # By niveau
        niveau_rows = (
            self.db.query(
                Document.niveau,
                sa_func.count(Document.id).label("count"),
            )
            .group_by(Document.niveau)
            .all()
        )
        par_niveau = {row.niveau: row.count for row in niveau_rows}

        return {
            "total_documents": total_docs,
            "total_validated": total_validated,
            "total_embedded": total_embedded,
            "par_matiere": par_matiere,
            "par_niveau": par_niveau,
        }

    # ── Private helpers ───────────────────────────────────────────

    def _recalculer_score_moyen(self, doc_id: int) -> Optional[float]:
        """Recalcule le score moyen depuis les durees de consultation des vues.
        Utilise la duree moyenne de consultation comme proxy d'engagement.
        """
        result = (
            self.db.query(sa_func.avg(DocumentView.duree_consultation_sec))
            .filter(
                DocumentView.document_id == doc_id,
                DocumentView.duree_consultation_sec.isnot(None),
            )
            .scalar()
        )
        if result is not None:
            avg_duration = float(result)
            # Update the document
            doc = (
                self.db.query(Document)
                .filter(Document.id == doc_id)
                .first()
            )
            if doc:
                doc.score_moyen_utilisateurs = round(avg_duration, 2)
                self.db.commit()
            return round(avg_duration, 2)
        return None
