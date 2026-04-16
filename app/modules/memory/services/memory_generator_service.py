"""
services/memory_generator_service.py (refondu)
===============================================
Génère des items mémoire bilingues (flashcard, qcm, cloze, short_answer)
depuis le texte d'un document. Utilise le LLM avec prompts structurés.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.modules.memory.services.base import MemoryBaseService
from app.modules.memory.models import MemorySection, MemoryItem
from app.modules.memory.utils.memory_item_generator import (
    _build_memory_prompt,
    parse_and_validate_items,
    compute_fingerprint,
)

logger = logging.getLogger(__name__)

# Types d'items supportés et leur nombre par défaut
ITEM_TYPES_CONFIG = {
    "flashcard": {"nb_default": 4, "description": "Question + réponse directe"},
    "qcm": {"nb_default": 3, "description": "Question à choix multiples"},
    "cloze": {"nb_default": 2, "description": "Phrase à compléter (____)"},
    "short_answer": {"nb_default": 2, "description": "Question ouverte courte"},
}


class MemoryGeneratorService(MemoryBaseService):
    """Génère des items mémoire bilingues depuis un document."""

    def __init__(self, db: Session, redis=None, llm_client=None):
        super().__init__(db, redis)
        self.llm_client = llm_client

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    async def generer_pack_section(
        self,
        document_id: int,
        section_title: str,
        texte_section: str,
        langue: str = "fr",
        niveau: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Génère des items mémoire pour un document.
        Détecte automatiquement les sections du document, puis génère
        des items pour chaque section détectée.

        Returns :
            {"nb_sections": int, "nb_items_generes": int, "sections": list}
        """
        from app.modules.epreuves.models import Document
        from app.modules.memory.utils.section_detector import detect_sections_from_text

        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if doc is None:
            raise ValueError(f"Document {document_id} not found")
        if doc.type_doc.lower() not in ("lecon", "cours", "resume"):
            raise ValueError(
                f"Document type '{doc.type_doc}' not supported. "
                f"Only 'lecon', 'cours', 'resume' are supported."
            )

        matiere = doc.matiere or "Autre"
        niveau_doc = niveau or doc.niveau or "Non specifie"
        serie_doc = doc.serie or ""

        # Détecter les sections automatiquement
        sections = detect_sections_from_text(texte_section)

        result = {"nb_sections": 0, "nb_items_generes": 0, "sections": []}

        for section in sections:
            # Créer ou récupérer la MemorySection
            memory_section = (
                self.db.query(MemorySection)
                .filter(
                    MemorySection.document_id == document_id,
                    MemorySection.section_title == section.title[:255],
                )
                .first()
            )
            if memory_section is None:
                memory_section = MemorySection(
                    document_id=document_id,
                    section_title=section.title[:255],
                    section_order=section.order,
                    section_summary=section.text[:500] if section.text else None,
                    generation_status="pending",
                )
                self.db.add(memory_section)
                self.db.flush()

            memory_section.generation_status = "generating"
            memory_section.generation_error = None
            self.db.commit()

            section_result = {
                "section_id": memory_section.id,
                "section_title": section.title,
                "nb_items": 0,
                "nb_par_type": {},
                "erreurs": [],
            }
            section_id = memory_section.id
            notion = doc.notion_principale or section.title

            # Générer les items pour cette section
            for item_type, config in ITEM_TYPES_CONFIG.items():
                nb_items = config["nb_default"]
                try:
                    items_data = await self._generer_items_type(
                        item_type=item_type,
                        nb_items=nb_items,
                        texte=section.text,
                        matiere=matiere,
                        niveau=niveau_doc,
                        serie=serie_doc,
                        notion=notion,
                    )
                    saved = 0
                    for item_data in items_data:
                        ok = self._sauvegarder_item_bilingue(
                            section_id=section_id,
                            item_type=item_type,
                            bilingual_item=item_data,
                        )
                        if ok:
                            saved += 1
                    section_result["nb_par_type"][item_type] = saved
                    section_result["nb_items"] += saved
                except Exception as exc:
                    logger.warning(f"Failed to generate {item_type} items: {exc}")
                    section_result["erreurs"].append(f"{item_type}: {exc}")
                    section_result["nb_par_type"][item_type] = 0

            # Finaliser le statut de la section
            total_expected = sum(c["nb_default"] for c in ITEM_TYPES_CONFIG.values())
            total_generated = section_result["nb_items"]

            if total_generated == 0:
                memory_section.generation_status = "failed"
                memory_section.generation_error = "; ".join(section_result["erreurs"])
            elif total_generated < total_expected:
                memory_section.generation_status = "partial"
            else:
                memory_section.generation_status = "complete"

            memory_section.nb_items = total_generated
            memory_section.generated_at = datetime.now(timezone.utc)
            self.db.commit()

            result["nb_sections"] += 1
            result["nb_items_generes"] += total_generated
            result["sections"].append(section_result)

        return result

    async def regenerer_section(self, section_id: int, force: bool = False) -> Dict[str, Any]:
        """Supprime les anciens items et régénère une section."""
        section = self.db.query(MemorySection).filter(MemorySection.id == section_id).first()
        if section is None:
            raise ValueError(f"MemorySection {section_id} not found")

        if not force and section.generation_status == "complete":
            return {"status": "already_complete", "message": "Section already complete; use force=True to regenerate."}

        # Supprimer les anciens items
        self.db.query(MemoryItem).filter(MemoryItem.section_id == section_id).delete()
        self.db.commit()

        # Régénérer
        return await self.generer_pack_section(
            document_id=section.document_id,
            section_title=section.section_title,
            texte_section=section.section_summary or "",
            langue="fr",
        )

    # ─────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────

    async def _generer_items_type(
        self,
        item_type: str,
        nb_items: int,
        texte: str,
        matiere: str,
        niveau: str,
        serie: str,
        notion: str,
    ) -> List[Dict[str, Any]]:
        """Génère des items d'un type spécifique via le LLM."""
        prompt = _build_memory_prompt(
            source_text=texte,
            item_type=item_type,
            batch_size=nb_items,
            matiere=matiere,
            niveau=niveau,
            serie=serie,
            notion=notion,
        )

        if self.llm_client is None:
            raise RuntimeError("LLM client not configured")

        response = await self.llm_client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=3000,
            response_format="json",
        )

        if response.get("error_code"):
            raise RuntimeError(f"LLM error: {response['error_code']}")

        text = response.get("text", "").strip()
        return parse_and_validate_items(text, item_type)

    def _sauvegarder_item_bilingue(
        self,
        section_id: int,
        item_type: str,
        bilingual_item: Dict[str, Any],
    ) -> bool:
        """Sauvegarde un item bilingue avec déduplication par fingerprint."""
        fr_content = bilingual_item.get("fr", {})
        fingerprint = compute_fingerprint(item_type, fr_content)

        existing = (
            self.db.query(MemoryItem)
            .filter(MemoryItem.section_id == section_id, MemoryItem.fingerprint == fingerprint)
            .first()
        )
        if existing is not None:
            return False

        # Content JSON : {"fr": {...}, "en": {...}}
        content_json = {"fr": fr_content, "en": bilingual_item.get("en", {})}

        new_item = MemoryItem(
            section_id=section_id,
            item_type=item_type,
            content_json=content_json,
            fingerprint=fingerprint,
        )
        self.db.add(new_item)
        return True
