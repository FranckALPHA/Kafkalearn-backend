"""
utils/memory_item_generator.py
===============================
Génération bilingue d'items mémoire (flashcard, qcm, cloze, short_answer).
Reprend la logique robuste de l'ancien code avec validation stricte.
"""
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Prompt templates par type d'item ──────────────────────────────

def _build_memory_prompt(
    source_text: str,
    item_type: str,
    batch_size: int,
    matiere: str = "inconnue",
    niveau: str = "inconnu",
    serie: str = "inconnu",
    notion: str = "inconnue",
) -> str:
    """Construit le prompt LLM pour un type d'item mémoire."""

    type_descriptions = {
        "flashcard": "question + answer (ex: 'Quelle est la formule de...?' / 'A_p^n = n!/(n-p)!')",
        "qcm": "question + options (4 choix) + answer (exactement l'une des options) + explanation",
        "cloze": "phrase à compléter avec ____ (4 underscores obligatoires) + answer (le mot/groupe à insérer)",
        "short_answer": "question ouverte courte + answer",
    }

    type_example = {
        "flashcard": '{"question": "Quelle est la formule de...", "answer": "f\'(x) = ...", "explanation": "...", "difficulty": "medium"}',
        "qcm": '{"question": "La dérivée de x² est...", "options": ["A. x", "B. 2x", "C. x²", "D. 2"], "answer": "B", "explanation": "...", "difficulty": "easy"}',
        "cloze": '{"question": "Le nombre d\'arrangements de p parmi n est ____.", "answer": "A_p^n = n!/(n-p)!", "difficulty": "hard"}',
        "short_answer": '{"question": "Définir la dérivée d\'une fonction.", "answer": "La dérivée est le taux de variation instantané...", "explanation": "...", "difficulty": "medium"}',
    }

    cloze_warning = ""
    if item_type == "cloze":
        cloze_warning = "\n\nREGLE CRITIQUE : la valeur 'question' DOIT contenir exactement ____ (4 underscores). Sans ____, l'item sera rejeté."

    prompt = f"""Tu génères des objets de mémorisation pour un élève camerounais.
Génère chaque item en DEUX LANGUES : FRANÇAIS et ANGLAIS.
Rends UNIQUEMENT du JSON valide (liste d'objets) sans markdown.

Format attendu par item :
{{
  "fr": {type_example[item_type]},
  "en": {{equivalent en anglais}}
}}

Contexte :
- matiere : {matiere}
- niveau : {niveau}
- serie : {serie}
- notion : {notion}
- type d'item : {item_type}
- description : {type_descriptions[item_type]}
- nombre d'items : {batch_size}
{cloze_warning}

Texte source :
\"\"\"
{source_text[:5000]}
\"\"\"
"""
    return prompt


# ─── Normalisation & validation ────────────────────────────────────

def _normalize_bilingual_item(raw: dict, item_type: str) -> Optional[dict]:
    """Normalise une version linguistique (fr ou en) d'un item."""
    question = str(raw.get("question") or "").strip()
    answer = str(raw.get("answer") or "").strip()
    explanation = str(raw.get("explanation") or "").strip() or None
    difficulty = str(raw.get("difficulty") or "").strip().lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"

    if len(question) < 6 or len(answer) < 1:
        return None

    options = None
    if item_type == "qcm":
        opt_list = raw.get("options")
        if not isinstance(opt_list, list) or len(opt_list) < 3:
            return None
        cleaned_options = [str(o).strip() for o in opt_list if str(o).strip()]
        # Vérifier que l'answer match une option
        answer_match = False
        for o in cleaned_options:
            if answer == o:
                answer_match = True
                break
            letter_match = re.match(r'^([A-Z])', o)
            if letter_match and answer == letter_match.group(1):
                answer_match = True
                break
        if not answer_match:
            return None
        options = cleaned_options[:6]

    elif item_type == "cloze":
        if "____" not in question:
            return None

    return {
        "question": question,
        "answer": answer,
        "options": options,
        "explanation": explanation,
        "difficulty": difficulty,
    }


def parse_and_validate_items(payload: str, item_type: str) -> List[dict]:
    """Parse le JSON brut du LLM et valide chaque item bilingue."""
    payload = payload.strip()

    # Extraire la liste JSON
    list_match = re.search(r'\[.*\]', payload, re.DOTALL)
    if list_match:
        payload = list_match.group(0)
    else:
        match = re.search(r"(\{.*?\}|\[.*?\])", payload, re.DOTALL)
        if match:
            payload = match.group(1)
        elif payload.startswith("```"):
            payload = payload.split("```", 2)[-2].strip()
            if payload.startswith("json"):
                payload = payload[4:].strip()

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        # Fallback : extraire un tableau valide
        try:
            match = re.search(r'\[[\s\S]{0,2000}\]', payload)
            if match:
                data = json.loads(match.group(0))
            else:
                data = []
        except Exception:
            data = []

    if isinstance(data, dict):
        data = data.get("items", [])
    if not isinstance(data, list):
        return []

    valid_items = []
    for d in data:
        if isinstance(d, dict) and "fr" in d and "en" in d:
            fr_data = _normalize_bilingual_item(d["fr"], item_type)
            en_data = _normalize_bilingual_item(d["en"], item_type)
            if fr_data and en_data:
                valid_items.append({"fr": fr_data, "en": en_data})

    return valid_items


# ─── Fingerprint & insertion ───────────────────────────────────────

def compute_fingerprint(item_type: str, content_fr: dict) -> str:
    """Calcule un fingerprint unique pour un item."""
    question = content_fr.get("question", "").lower()
    answer = content_fr.get("answer", "").lower()
    source = f"{item_type}|{question}|{answer}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
