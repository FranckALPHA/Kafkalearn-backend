import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from redis import Redis
from sqlalchemy.orm import Session

from app.modules.memory.services.base import MemoryBaseService
from app.modules.memory.models import MemorySection, MemoryItem
from app.modules.memory.utils import PromptTemplates, TextNormalizer
from app.modules.memory.utils.constants import ITEM_TYPES_CONFIG

logger = logging.getLogger(__name__)


class MemoryGeneratorService(MemoryBaseService):
    """Service responsible for generating memory items (flashcards, QCM, cloze, short_answer) from document sections."""

    def __init__(self, db: Session, redis: Redis = None, llm_client=None):
        super().__init__(db, redis)
        self.llm_client = llm_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generer_pack_section(
        self,
        document_id: int,
        section_title: str,
        texte_section: str,
        langue: str = "fr",
        niveau: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a full pack of memory items for a document section.

        Returns:
            dict with keys: nb_items_generes, nb_par_type, erreurs
        """
        # 1. Validate document is a "lecon"
        from app.modules.epreuves.models import Document

        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if doc is None:
            raise ValueError(f"Document {document_id} not found")
        if doc.type_doc != "lecon":
            raise ValueError(
                f"Document type '{doc.type_doc}' is not 'lecon'; memory generation requires a lesson."
            )

        # 2. Create or update MemorySection
        section = (
            self.db.query(MemorySection)
            .filter(
                MemorySection.document_id == document_id,
                MemorySection.section_title == section_title,
            )
            .first()
        )
        if section is None:
            section = MemorySection(
                document_id=document_id,
                section_title=section_title,
                section_order=0,
                section_summary=texte_section[:500] if texte_section else None,
                generation_status="pending",
            )
            self.db.add(section)
            self.db.flush()

        # 3. Mark as generating
        section.generation_status = "generating"
        section.generation_error = None
        self.db.commit()

        result: Dict[str, Any] = {
            "nb_items_generes": 0,
            "nb_par_type": {},
            "erreurs": [],
        }
        section_id = section.id

        try:
            for item_type, config in ITEM_TYPES_CONFIG.items():
                nb_items = config["nb_default"]
                try:
                    items_data = await self._generer_items_type(
                        item_type=item_type,
                        nb_items=nb_items,
                        texte=texte_section,
                        langue=langue,
                        niveau=niveau or doc.niveau,
                    )
                    saved = 0
                    for item_data in items_data:
                        ok = await self._sauvegarder_item(
                            section_id=section_id,
                            item_type=item_type,
                            item_data=item_data,
                            langue=langue,
                        )
                        if ok:
                            saved += 1
                    result["nb_par_type"][item_type] = saved
                    result["nb_items_generes"] += saved
                except Exception as exc:
                    logger.warning("Failed to generate %s items: %s", item_type, exc)
                    result["erreurs"].append(f"{item_type}: {exc}")
                    result["nb_par_type"][item_type] = 0

            # 4. Finalize status
            total_expected = sum(c["nb_default"] for c in ITEM_TYPES_CONFIG.values())
            total_generated = result["nb_items_generes"]
            if total_generated == 0:
                section.generation_status = "failed"
                section.generation_error = "; ".join(result["erreurs"])
            elif total_generated < total_expected:
                section.generation_status = "partial"
            else:
                section.generation_status = "complete"

            section.nb_items = total_generated
            section.generated_at = datetime.now(timezone.utc)
            self.db.commit()

        except Exception as exc:
            logger.error("Memory generation failed: %s", exc, exc_info=True)
            section.generation_status = "failed"
            section.generation_error = str(exc)
            self.db.commit()
            result["erreurs"].append(str(exc))

        return result

    async def regenerer_section(self, section_id: int, force: bool = False) -> Dict[str, Any]:
        """Delete old items and re-generate a section."""
        section = self.db.query(MemorySection).filter(MemorySection.id == section_id).first()
        if section is None:
            raise ValueError(f"MemorySection {section_id} not found")

        if not force and section.generation_status == "complete":
            return {"status": "already_complete", "message": "Section is already complete; use force=True to regenerate."}

        # Delete existing items
        self.db.query(MemoryItem).filter(MemoryItem.section_id == section_id).delete()
        self.db.commit()

        # Re-generate
        return await self.generer_pack_section(
            document_id=section.document_id,
            section_title=section.section_title,
            texte_section=section.section_summary or "",
            langue="fr",
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _generer_items_type(
        self,
        item_type: str,
        nb_items: int,
        texte: str,
        langue: str,
        niveau: str,
    ) -> List[Dict[str, Any]]:
        """Generate items of a specific type via the LLM."""
        # Build prompt
        prompt_method = getattr(PromptTemplates, f"for_{item_type}", None)
        if prompt_method is None:
            raise ValueError(f"Unknown item type: {item_type}")

        prompt_template = prompt_method(nb=nb_items, langue=langue, niveau=niveau)
        prompt = prompt_template.replace("{texte_section}", texte)

        # Call LLM
        if self.llm_client is None:
            raise RuntimeError("LLM client not configured")

        response = await self.llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            system_instruction=PromptTemplates.BASE_SYSTEM,
            response_format="json",
        )

        if response.get("error_code"):
            raise RuntimeError(f"LLM error: {response['error_code']}")

        # Parse JSON
        import json

        text = response.get("text", "").strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```", 2)[-2].strip()
            if text.startswith("json"):
                text = text[4:].strip()

        items = json.loads(text)
        if not isinstance(items, list):
            raise ValueError(f"Expected a JSON array, got {type(items).__name__}")

        return items

    async def _sauvegarder_item(
        self,
        section_id: int,
        item_type: str,
        item_data: Dict[str, Any],
        langue: str,
    ) -> bool:
        """Save a single memory item, deduplicating via fingerprint.

        Returns True if a new item was created, False if duplicate.
        """
        # Build content_json
        content_json = {langue: item_data}

        # Compute fingerprint
        question = item_data.get("question") or item_data.get("recto") or item_data.get("enonce") or ""
        answer = item_data.get("answer") or item_data.get("verso") or item_data.get("bonne_reponse") or ""
        raw = TextNormalizer.normalize(f"{item_type}:{question}:{answer}")
        fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        # Check duplicate
        existing = (
            self.db.query(MemoryItem)
            .filter(MemoryItem.section_id == section_id, MemoryItem.fingerprint == fingerprint)
            .first()
        )
        if existing is not None:
            logger.debug("Duplicate item skipped (fingerprint=%s)", fingerprint[:8])
            return False

        new_item = MemoryItem(
            section_id=section_id,
            item_type=item_type,
            content_json=content_json,
            fingerprint=fingerprint,
        )
        self.db.add(new_item)
        return True

    @staticmethod
    def _estimer_difficulte(difficulte_str: Optional[str]) -> float:
        """Map a difficulty string to a float in [0, 1]."""
        mapping = {
            "facile": 0.3,
            "moyen": 0.5,
            "difficile": 0.7,
        }
        return mapping.get(difficulte_str, 0.5) if difficulte_str else 0.5
