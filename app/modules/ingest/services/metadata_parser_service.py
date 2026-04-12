import json
import logging

from app.modules.ingest.services.base import IngestBaseService

logger = logging.getLogger(__name__)


class MetadataParserService(IngestBaseService):
    async def extraire_metadata(self, texte: str, nom_fichier: str) -> tuple:
        """
        Extract metadata from document text using LLM.
        Returns (metadata_dict, confidence_score).
        """
        try:
            from app.modules.core.education.llm_client import generate_text
            from app.modules.ingest.utils import EducationNormalizer

            normalizer = EducationNormalizer()

            prompt = self._build_extraction_prompt(texte, nom_fichier)

            llm_response = await generate_text(prompt)

            # Parse JSON from LLM response
            metadata = self._parse_llm_response(llm_response)

            if not metadata:
                return {}, 0.0

            # Normalize matiere and niveau
            if "matiere" in metadata:
                metadata["matiere"] = normalizer.normaliser_matiere(metadata["matiere"])
            if "niveau" in metadata:
                metadata["niveau"] = normalizer.normaliser_niveau(metadata["niveau"])

            # Calculate confidence based on filled fields
            confidence = self._calculer_confiance(metadata)

            return metadata, confidence

        except Exception as exc:
            logger.error(f"Metadata extraction failed for {nom_fichier}: {exc}")
            return {}, 0.0

    def _build_extraction_prompt(self, texte: str, nom_fichier: str) -> str:
        """Build the LLM prompt for metadata extraction."""
        # Truncate text if too long
        texte_sample = texte[:4000] if texte else ""

        return f"""You are an expert in educational document analysis. Extract metadata from the following document.

Document name: {nom_fichier}

Text excerpt:
{texte_sample}

Extract the following metadata and return a JSON object:
- matiere: subject (Mathematiques, Physique, SVT, Francais, Histoire-Geographie, Philosophie, Informatique, etc.)
- niveau: education level (Terminale, Premiere, Seconde, 3eme, etc.)
- type_doc: document type (epreuve, exercice, cours, corrige, serie, etc.)
- annee: year (integer, e.g. 2024, 2025, 2026)
- serie: series/filiere (C, D, TI, A, B, etc. or null)
- sous_type: sub-type (devoir, examen, concours, exercice, etc. or null)
- notion_principale: main concept/topic covered (string or null)
- mots_cles: list of keywords (array of strings)
- difficulte_estimee: estimated difficulty (facile, moyen, difficile or null)
- langue: language code (fr, en, etc.)

Return ONLY a valid JSON object, nothing else."""

    def _parse_llm_response(self, response: str) -> dict:
        """Parse JSON from LLM response."""
        try:
            # Try to extract JSON from the response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start == -1 or end == 0:
                return {}

            json_str = response[start:end]
            data = json.loads(json_str)
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"Failed to parse LLM JSON response: {exc}")
            return {}

    def _calculer_confiance(self, metadata: dict) -> float:
        """
        Calculate confidence score based on filled fields.
        Key fields: matiere, niveau, type_doc, annee, serie
        """
        key_fields = ["matiere", "niveau", "type_doc", "annee", "serie"]
        filled = sum(1 for field in key_fields if metadata.get(field))
        total = len(key_fields)

        # Base confidence from key fields ratio
        confidence = filled / total

        # Bonus for additional filled fields
        extra_fields = ["notion_principale", "mots_cles", "difficulte_estimee"]
        extra_filled = sum(1 for field in extra_fields if metadata.get(field))
        confidence += extra_filled * 0.05

        return min(round(confidence, 2), 1.0)
