import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.doc_analysis.models import DocumentAnalysis, AnalysisFeedback
from app.modules.doc_analysis.services.base import DocAnalysisBaseService
from app.modules.doc_analysis.utils import HashUtils

logger = logging.getLogger(__name__)


class AnalysisCacheService(DocAnalysisBaseService):
    def __init__(self, db):
        super().__init__(db)

    async def verifier_coherence_hash(self, document_id: int) -> dict:
        from app.modules.epreuves.models.document import Document

        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} introuvable")

        current_hash = HashUtils.hash_document_text(document.texte_extrait or "")
        analyses = (
            self.db.query(DocumentAnalysis)
            .filter(DocumentAnalysis.document_id == document_id)
            .all()
        )

        analyses_data = []
        nb_obsoletes = 0

        for analysis in analyses:
            is_coherent = HashUtils.hashes_match(analysis.document_hash, current_hash)
            if not is_coherent:
                nb_obsoletes += 1
            analyses_data.append({
                **analysis.serialize(),
                "is_coherent": is_coherent,
            })

        return {
            "coherent": nb_obsoletes == 0,
            "nb_analyses_obsoletes": nb_obsoletes,
            "analyses": analyses_data,
        }

    async def invalider_analyses_document(self, document_id: int) -> int:
        from app.modules.epreuves.models.document import Document

        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} introuvable")

        current_hash = HashUtils.hash_document_text(document.texte_extrait or "")
        obsolete_analyses = (
            self.db.query(DocumentAnalysis)
            .filter(
                DocumentAnalysis.document_id == document_id,
                ~DocumentAnalysis.document_hash == current_hash,
            )
            .all()
        )

        count = len(obsolete_analyses)
        for analysis in obsolete_analyses:
            self.db.delete(analysis)

        if count > 0:
            self.db.commit()

        logger.info(f"Invalidated {count} obsolete analyses for document {document_id}")
        return count

    async def obtenir_stats_cache(self) -> dict:
        total_analyses = (
            self.db.query(func.count(DocumentAnalysis.id)).scalar() or 0
        )

        total_feedbacks = (
            self.db.query(func.count(AnalysisFeedback.id)).scalar() or 0
        )

        feedbacks_utiles = (
            self.db.query(func.count(AnalysisFeedback.id))
            .filter(AnalysisFeedback.est_utile == True)
            .scalar() or 0
        )

        taux_utilite_global = (
            round(feedbacks_utiles / total_feedbacks, 4)
            if total_feedbacks > 0
            else None
        )

        all_analyses = self.db.query(DocumentAnalysis).all()
        low_quality_count = 0
        for analysis in all_analyses:
            if analysis.taux_utilite is not None and analysis.taux_utilite < 0.35:
                total_fb = analysis.feedback_utile + analysis.feedback_pas_utile
                if total_fb >= 5:
                    low_quality_count += 1

        total_accesses = (
            self.db.query(func.sum(DocumentAnalysis.nb_acces)).scalar() or 0
        )

        return {
            "total_analyses": total_analyses,
            "total_accesses": total_accesses,
            "total_feedbacks": total_feedbacks,
            "feedbacks_utiles": feedbacks_utiles,
            "taux_utilite_global": taux_utilite_global,
            "low_quality_analyses_count": low_quality_count,
        }
