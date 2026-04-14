"""
utils/section_detector.py
==========================
Détecte automatiquement les sections d'un document à partir du texte extrait.
Utilise des patterns regex (EXERCICE, PARTIE, CHAPITRE, I., II., etc.) + LLM fallback.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DetectedSection:
    title: str
    start_pos: int
    end_pos: int
    text: str
    order: int


# ─── Patterns de détection (programme camerounais) ────────────────

SECTION_PATTERNS = [
    # EXERCICE 1:, EXERCICE 2:, Exercice 1, EXERCICE N°1
    r'(?i)(?:^|\n)\s*E?X?E?R?C?I?C?E\s*[:.]?\s*\d*\s*[^:\n]*',
    # PARTIE A:, PARTIE I:, PARTIE 1:
    r'(?i)(?:^|\n)\s*PARTIE\s+[A-Z0-9IVXLCDM]+\s*[:.]?\s*[^:\n]*',
    # CHAPITRE 1:, CHAPITRE I:
    r'(?i)(?:^|\n)\s*CHAPITRE\s+[A-Z0-9IVXLCDM]+\s*[:.]?\s*[^:\n]*',
    # I., II., III., IV., V. (en début de ligne)
    r'(?i)(?:^|\n)\s*[IVX]+\.?\s+[A-Z][^.\n]{5,60}',
    # A), B), C) en début de section majeure
    r'(?i)(?:^|\n)\s*[A-Z]\)\s+[A-Z][^.\n]{5,60}',
    # QUESTIONS: ou QUESTION 1:
    r'(?i)(?:^|\n)\s*QUESTIONS?\s*[:.]?\s*\d*\s*[^:\n]*',
    # PROBLÈME 1:
    r'(?i)(?:^|\n)\s*PROBL[EÈ]ME\s*[:.]?\s*\d*\s*[^:\n]*',
    # SÉQUENCE 1:
    r'(?i)(?:^|\n)\s*S[EÉ]QUENCE\s*[:.]?\s*\d*\s*[^:\n]*',
    # LEÇON 1:
    r'(?i)(?:^|\n)\s*LE[ÇC]ON\s*[:.]?\s*\d*\s*[^:\n]*',
]


def detect_sections_from_text(
    texte: str,
    min_section_length: int = 200,
    max_sections: int = 15,
) -> List[DetectedSection]:
    """
    Détecte les sections d'un document via des patterns regex.
    Fallback : si aucun pattern trouvé → 1 seule section globale.
    """
    if not texte or len(texte.strip()) < min_section_length:
        return [DetectedSection(
            title="Contenu principal",
            start_pos=0,
            end_pos=len(texte),
            text=texte,
            order=0,
        )]

    # Collecter toutes les positions de début de section
    boundaries = []
    for pattern in SECTION_PATTERNS:
        for match in re.finditer(pattern, texte):
            title = match.group(0).strip()
            # Nettoyer le titre
            title = re.sub(r'\s+', ' ', title)
            title = title[:80]  # Limiter la longueur
            boundaries.append((match.start(), title))

    if not boundaries:
        # Aucun pattern trouvé → section unique
        return [DetectedSection(
            title="Contenu principal",
            start_pos=0,
            end_pos=len(texte),
            text=texte,
            order=0,
        )]

    # Trier par position et dédupliquer les positions proches
    boundaries.sort(key=lambda x: x[0])
    deduped = [boundaries[0]]
    for pos, title in boundaries[1:]:
        if pos - deduped[-1][0] > 50:  # Au moins 50 chars entre sections
            deduped.append((pos, title))

    # Créer les sections
    sections = []
    for i, (start, title) in enumerate(deduped[:max_sections]):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(texte)
        section_text = texte[start:end].strip()

        if len(section_text) >= min_section_length:
            sections.append(DetectedSection(
                title=title,
                start_pos=start,
                end_pos=end,
                text=section_text,
                order=i,
            ))

    # Si aucune section valide → fallback
    if not sections:
        return [DetectedSection(
            title="Contenu principal",
            start_pos=0,
            end_pos=len(texte),
            text=texte,
            order=0,
        )]

    return sections


def detect_sections_llm_fallback(texte: str) -> List[Dict]:
    """
    Fallback LLM pour détecter les sections quand les regex échouent.
    Utilisé uniquement si detect_sections_from_text retourne 1 section
    et que le texte est long (> 2000 chars).
    """
    if len(texte) < 2000:
        return []

    from app.modules.skills.utils.llm_client import LLMClient, LLMProvider
    from app.core.config import OPENROUTER_API_KEYS
    import json

    prompt = f"""Détecte les sections/chapitres de ce document scolaire camerounais.
Retourne UNIQUEMENT un JSON avec cette structure :
{{"sections": [{{"title": "Titre de la section", "start_keyword": "premier mot ou phrase de la section"}}]}}

Document (extrait) :
\"\"\"
{texte[:3000]}
\"\"\"
"""
    try:
        api_keys = {"openrouter_api_keys": [k for k in OPENROUTER_API_KEYS if k]}
        client = LLMClient(api_keys, default_provider=LLMProvider.OPENROUTER)
        response = client.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
            response_format="json",
        )

        text = response.get("text", "").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[-2].strip()
            if text.startswith("json"):
                text = text[4:].strip()

        result = json.loads(text)
        return result.get("sections", [])

    except Exception as e:
        logger.warning(f"LLM section detection failed: {e}")
        return []
