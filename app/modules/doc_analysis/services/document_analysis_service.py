import logging
import time
from datetime import datetime
from typing import Optional

from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import REDIS_URL
from app.modules.doc_analysis.models import DocumentAnalysis, AnalysisFeedback
from app.modules.doc_analysis.services.base import DocAnalysisBaseService
from app.modules.doc_analysis.utils import PromptBuilder, JSONValidator, HashUtils
from app.modules.doc_analysis.utils.constants import REFRESH_TTL_SECONDS
from app.modules.epreuves.models.document import Document

logger = logging.getLogger(__name__)


class DocumentAnalysisService(DocAnalysisBaseService):
    CURRENT_VERSION = "v1"

    def __init__(self, db: Session, redis: Redis = None):
        super().__init__(db, redis)

    async def analyser_ou_retourner_cache(
        self,
        document_id: int,
        langue: str,
        user_plan: str = "freemium",
    ) -> dict:
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} introuvable")

        existing = (
            self.db.query(DocumentAnalysis)
            .filter(
                DocumentAnalysis.document_id == document_id,
                DocumentAnalysis.langue == langue,
            )
            .first()
        )

        current_hash = HashUtils.hash_document_text(document.texte_extrait or "")

        if existing and HashUtils.hashes_match(existing.document_hash, current_hash):
            existing.nb_acces += 1
            self.db.commit()

            try:
                from app.modules.epreuves.jobs.tasks import increment_document_stat_task
                increment_document_stat_task.delay(document_id, "nb_acces")
            except Exception as exc:
                logger.warning(f"Celery task increment failed: {exc}")

            return {**existing.serialize(), "is_cached": True}

        analyse = await self.generer_analyse(document, langue)

        now = datetime.utcnow()
        new_analysis = DocumentAnalysis(
            document_id=document_id,
            langue=langue,
            document_hash=current_hash,
            analysis_type=document.type_doc if hasattr(document, "type_doc") else "epreuve",
            analysis_version=self.CURRENT_VERSION,
            key_points=analyse.get("key_points", []),
            concepts=analyse.get("concepts", []),
            tips=analyse.get("tips", []),
            summary=analyse.get("summary"),
            methodologie=analyse.get("methodologie"),
            difficulte_detail=analyse.get("difficulte_detail", {}),
            notions_prerequis=analyse.get("notions_prerequis", []),
            llm_provider=analyse.get("llm_provider"),
            latence_ms=analyse.get("latence_ms"),
            created_at=now,
            updated_at=now,
            analyzed_at=now,
        )
        self.db.add(new_analysis)

        self.db.commit()
        self.db.refresh(new_analysis)

        return {**new_analysis.serialize(), "is_cached": False}

    async def generer_analyse(self, document, langue: str) -> dict:
        document_dict = {
            "matiere": getattr(document, "matiere", "?"),
            "niveau": getattr(document, "niveau", "?"),
            "serie": getattr(document, "serie", "?"),
            "texte_extrait": getattr(document, "texte_extrait", "") or "",
        }
        analysis_type = getattr(document, "type_doc", "epreuve") or "epreuve"

        system_prompt = PromptBuilder.build_system_prompt(analysis_type, langue)
        user_prompt = PromptBuilder.build_user_prompt(document_dict)

        start_ms = int(time.time() * 1000)
        llm_provider_name = None
        raw_response = None

        try:
            from app.modules.skills.utils.llm_client import LLMClient

            llm_client = LLMClient()
            raw_response = await llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            llm_provider_name = getattr(llm_client, "provider", "unknown")
        except Exception as exc:
            logger.error(f"LLM generation failed: {exc}")
            raise RuntimeError(f"Echec de la generation LLM: {exc}")

        elapsed_ms = int(time.time() * 1000) - start_ms

        validated = JSONValidator.parse_and_validate(raw_response, analysis_type)
        validated["llm_provider"] = llm_provider_name
        validated["latence_ms"] = elapsed_ms

        return validated

    async def forcer_regeneration(
        self,
        document_id: int,
        langue: str,
        user_id: str,
    ) -> dict:
        rate_limit_key = f"doc_analysis:refresh:{user_id}:{document_id}"
        if self.redis.exists(rate_limit_key):
            raise PermissionError("Regeneration rate limit: 1 per 24h per document")

        self.redis.setex(rate_limit_key, REFRESH_TTL_SECONDS, "1")

        old_analysis = (
            self.db.query(DocumentAnalysis)
            .filter(
                DocumentAnalysis.document_id == document_id,
                DocumentAnalysis.langue == langue,
            )
            .first()
        )
        if old_analysis:
            self.db.delete(old_analysis)
            self.db.commit()

        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} introuvable")

        analyse = await self.generer_analyse(document, langue)

        current_hash = HashUtils.hash_document_text(document.texte_extrait or "")
        now = datetime.utcnow()
        new_analysis = DocumentAnalysis(
            document_id=document_id,
            langue=langue,
            document_hash=current_hash,
            analysis_type=getattr(document, "type_doc", "epreuve") or "epreuve",
            analysis_version=self.CURRENT_VERSION,
            key_points=analyse.get("key_points", []),
            concepts=analyse.get("concepts", []),
            tips=analyse.get("tips", []),
            summary=analyse.get("summary"),
            methodologie=analyse.get("methodologie"),
            difficulte_detail=analyse.get("difficulte_detail", {}),
            notions_prerequis=analyse.get("notions_prerequis", []),
            llm_provider=analyse.get("llm_provider"),
            latence_ms=analyse.get("latence_ms"),
            created_at=now,
            updated_at=now,
            analyzed_at=now,
            refreshed_at=now,
        )
        self.db.add(new_analysis)
        self.db.commit()
        self.db.refresh(new_analysis)

        return new_analysis.serialize()

    async def obtenir_analyse_existante(
        self,
        document_id: int,
        langue: str,
    ) -> Optional[dict]:
        existing = (
            self.db.query(DocumentAnalysis)
            .filter(
                DocumentAnalysis.document_id == document_id,
                DocumentAnalysis.langue == langue,
            )
            .first()
        )
        if not existing:
            return None

        existing.nb_acces += 1
        self.db.commit()

        return existing.serialize()
