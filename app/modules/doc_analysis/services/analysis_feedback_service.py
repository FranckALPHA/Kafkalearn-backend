import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.doc_analysis.models import DocumentAnalysis, AnalysisFeedback
from app.modules.doc_analysis.services.base import DocAnalysisBaseService
from app.modules.doc_analysis.utils.constants import ALERT_THRESHOLD_RATE, MIN_FEEDBACKS_FOR_ALERT

logger = logging.getLogger(__name__)


class AnalysisFeedbackService(DocAnalysisBaseService):
    def __init__(self, db):
        super().__init__(db)

    async def enregistrer_feedback(
        self,
        analysis_id: int,
        user_id: str,
        est_utile: bool,
        section_problematique: Optional[str] = None,
        commentaire: Optional[str] = None,
    ) -> dict:
        analysis = (
            self.db.query(DocumentAnalysis)
            .filter(DocumentAnalysis.id == analysis_id)
            .first()
        )
        if not analysis:
            raise ValueError(f"Analysis {analysis_id} introuvable")

        existing_feedback = (
            self.db.query(AnalysisFeedback)
            .filter(
                AnalysisFeedback.analysis_id == analysis_id,
                AnalysisFeedback.user_id == user_id,
            )
            .first()
        )

        if existing_feedback:
            existing_feedback.est_utile = est_utile
            existing_feedback.section_problematique = section_problematique
            existing_feedback.commentaire = commentaire
            existing_feedback.updated_at = datetime.utcnow()
            
            # Update counts if the feedback value changed
            if existing_feedback.est_utile != est_utile:
                if est_utile:
                    analysis.feedback_utile += 1
                    analysis.feedback_pas_utile -= 1
                else:
                    analysis.feedback_pas_utile += 1
                    analysis.feedback_utile -= 1
        else:
            new_feedback = AnalysisFeedback(
                analysis_id=analysis_id,
                user_id=user_id,
                est_utile=est_utile,
                section_problematique=section_problematique,
                commentaire=commentaire,
            )
            self.db.add(new_feedback)
            
            # Increment the appropriate counter for new feedback
            if est_utile:
                analysis.feedback_utile += 1
            else:
                analysis.feedback_pas_utile += 1

        self.db.commit()
        self.db.refresh(analysis)

        await self._verifier_seuil_alerte(analysis)

        return {
            "analysis_id": analysis_id,
            "taux_utilite": analysis.taux_utilite,
            "feedback_utile": analysis.feedback_utile,
            "feedback_pas_utile": analysis.feedback_pas_utile,
        }

    async def obtenir_analyses_faible_qualite(
        self,
        seuil_taux_utilite: float = 0.35,
        nb_feedbacks_min: int = 5,
    ) -> list:
        analyses = (
            self.db.query(DocumentAnalysis)
            .filter(
                DocumentAnalysis.feedback_utile + DocumentAnalysis.feedback_pas_utile >= nb_feedbacks_min,
            )
            .all()
        )
        return [
            a.serialize()
            for a in analyses
            if a.taux_utilite is not None and a.taux_utilite < seuil_taux_utilite
        ]

    async def taux_utilite_global(self, periode_jours: int = 30) -> dict:
        since = datetime.utcnow() - timedelta(days=periode_jours)
        feedbacks = (
            self.db.query(AnalysisFeedback)
            .filter(AnalysisFeedback.created_at >= since)
            .all()
        )
        if not feedbacks:
            return {
                "total_feedbacks": 0,
                "feedbacks_utiles": 0,
                "taux_utilite_global": None,
                "periode_jours": periode_jours,
            }

        utiles = sum(1 for f in feedbacks if f.est_utile)
        total = len(feedbacks)

        return {
            "total_feedbacks": total,
            "feedbacks_utiles": utiles,
            "taux_utilite_global": round(utiles / total, 4) if total > 0 else None,
            "periode_jours": periode_jours,
        }

    async def _verifier_seuil_alerte(self, analysis: DocumentAnalysis) -> None:
        total = analysis.feedback_utile + analysis.feedback_pas_utile
        if total < MIN_FEEDBACKS_FOR_ALERT:
            return

        taux_pas_utile = analysis.feedback_pas_utile / total if total > 0 else 0
        if taux_pas_utile > ALERT_THRESHOLD_RATE:
            logger.warning(
                f"Analysis {analysis.id} has low quality: "
                f"taux_pas_utile={taux_pas_utile:.2%}, "
                f"total_feedbacks={total}"
            )
