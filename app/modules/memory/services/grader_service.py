import logging
import re
from typing import Any, Dict, Optional

from app.modules.memory.services.base import MemoryBaseService
from app.modules.memory.utils import TextNormalizer

logger = logging.getLogger(__name__)


class GraderService(MemoryBaseService):
    """Service responsible for grading user responses on memory items."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def noter(
        self,
        item,
        reponse_utilisateur: Optional[str] = None,
        qualite_flashcard: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Grade a user response for a memory item.

        Routes to the type-specific grader.
        Returns dict with score (0-5), est_correct (bool), and details.
        """
        item_type = item.item_type
        content = item.get_content_for_language("fr")

        if item_type == "qcm":
            return self._noter_qcm(content, reponse_utilisateur)
        elif item_type == "cloze":
            return self._noter_cloze(content, reponse_utilisateur)
        elif item_type == "short_answer":
            return self._noter_short_answer(content, reponse_utilisateur)
        elif item_type == "flashcard":
            return self._noter_flashcard(content, qualite_flashcard)
        else:
            raise ValueError(f"Unknown item type for grading: {item_type}")

    # ------------------------------------------------------------------
    # Type-specific graders
    # ------------------------------------------------------------------

    @staticmethod
    def _noter_qcm(content: Dict[str, Any], reponse: Optional[str]) -> Dict[str, Any]:
        """Grade a QCM response.

        Exact match after normalization; also tries index mapping (A/1 -> 0, B/2 -> 1, ...).
        """
        if not reponse:
            return {"score": 0, "est_correct": False, "details": "No response provided"}

        bonne_reponse = content.get("bonne_reponse", "")
        options = content.get("options", [])

        # Normalize both
        normalized_user = TextNormalizer.normalize(reponse)
        normalized_correct = TextNormalizer.normalize(bonne_reponse)

        # Exact match
        if normalized_user == normalized_correct:
            return {"score": 5, "est_correct": True, "details": "Exact match"}

        # Try index mapping: A/1 -> index 0, B/2 -> index 1, etc.
        user_answer_index = GraderService._parse_qcm_index(reponse)
        correct_answer_index = GraderService._parse_qcm_index(bonne_reponse)

        if user_answer_index is not None and correct_answer_index is not None:
            if user_answer_index == correct_answer_index:
                return {"score": 5, "est_correct": True, "details": "Index match"}
            else:
                return {
                    "score": 0,
                    "est_correct": False,
                    "details": f"Wrong index: expected {correct_answer_index}, got {user_answer_index}",
                }

        # Fuzzy: check if user response is a substring of the correct answer or vice versa
        if normalized_user in normalized_correct or normalized_correct in normalized_user:
            return {"score": 3, "est_correct": True, "details": "Substring match"}

        return {"score": 0, "est_correct": False, "details": "No match"}

    @staticmethod
    def _noter_cloze(content: Dict[str, Any], reponse: Optional[str]) -> Dict[str, Any]:
        """Grade a cloze (fill-in-the-blank) response.

        Matches against alternatives separated by |.
        """
        if not reponse:
            return {"score": 0, "est_correct": False, "details": "No response provided"}

        alternatives_str = content.get("alternatives", "")
        if not alternatives_str:
            # Fall back to checking enonce for the blank
            return {"score": 0, "est_correct": False, "details": "No alternatives defined"}

        alternatives = [alt.strip() for alt in alternatives_str.split("|") if alt.strip()]
        normalized_user = TextNormalizer.normalize(reponse)

        for alt in alternatives:
            if TextNormalizer.normalize(alt) == normalized_user:
                return {"score": 5, "est_correct": True, "details": "Exact match with alternative"}

        # Partial: token overlap
        best_overlap = 0.0
        for alt in alternatives:
            t1 = set(normalized_user.split())
            t2 = set(TextNormalizer.normalize(alt).split())
            if t1 and t2:
                overlap = len(t1 & t2) / len(t1 | t2)
                best_overlap = max(best_overlap, overlap)

        if best_overlap >= 0.6:
            return {"score": 3, "est_correct": True, "details": f"Token overlap: {best_overlap:.0%}"}

        return {"score": 0, "est_correct": False, "details": "No match"}

    @staticmethod
    def _noter_short_answer(content: Dict[str, Any], reponse: Optional[str]) -> Dict[str, Any]:
        """Grade a short-answer response.

        Exact match -> 5, 60% token overlap -> 3, substring match -> 3, else -> 1.
        """
        if not reponse:
            return {"score": 0, "est_correct": False, "details": "No response provided"}

        bonne_reponse = content.get("bonne_reponse", "")
        normalized_user = TextNormalizer.normalize(reponse)
        normalized_correct = TextNormalizer.normalize(bonne_reponse)

        # Exact match
        if normalized_user == normalized_correct:
            return {"score": 5, "est_correct": True, "details": "Exact match"}

        # Token overlap (60% threshold)
        t1 = set(normalized_user.split())
        t2 = set(normalized_correct.split())
        if t1 and t2:
            overlap = len(t1 & t2) / len(t1 | t2)
            if overlap >= 0.6:
                return {"score": 3, "est_correct": True, "details": f"Token overlap: {overlap:.0%}"}

        # Substring match
        if TextNormalizer.substring_match(bonne_reponse, reponse):
            return {"score": 3, "est_correct": True, "details": "Substring match"}

        return {"score": 1, "est_correct": False, "details": "No meaningful match"}

    @staticmethod
    def _noter_flashcard(content: Dict[str, Any], qualite: Optional[int]) -> Dict[str, Any]:
        """Grade a flashcard response based on self-reported quality (0-5)."""
        if qualite is None:
            return {"score": 0, "est_correct": False, "details": "No quality rating provided"}

        if not (0 <= qualite <= 5):
            raise ValueError(f"Flashcard quality must be between 0 and 5, got {qualite}")

        return {
            "score": qualite,
            "est_correct": qualite >= 3,
            "qualite_reponse": qualite,
            "details": f"Self-reported quality: {qualite}/5",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_qcm_index(reponse: str) -> Optional[int]:
        """Try to parse a QCM answer as an index (A/a/1 -> 0, B/b/2 -> 1, ...)."""
        reponse = reponse.strip().upper()
        # Letter mapping
        if re.match(r"^[A-D]$", reponse):
            return ord(reponse) - ord("A")
        # Numeric mapping (1-indexed)
        if re.match(r"^[1-4]$", reponse):
            return int(reponse) - 1
        return None
