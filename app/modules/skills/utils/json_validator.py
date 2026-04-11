"""
utils/json_validator.py
=======================
Validation stricte des sorties JSON du LLM.
"""
import logging
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)


def validate_quiz_json(data: Dict[str, Any], type_quiz: str, expected_nb: int) -> Tuple[bool, List[str]]:
    """
    Valide la structure d'un quiz généré par le LLM.

    Returns:
        (is_valid, errors)
    """
    errors = []

    # Champs requis
    required_fields = ["titre", "matiere", "niveau", "questions"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Champ manquant: {field}")

    if errors:
        return False, errors

    # Validation des questions
    questions = data.get("questions", [])
    if not isinstance(questions, list):
        return False, ["'questions' doit être une liste"]

    if len(questions) != expected_nb:
        errors.append(f"Nombre de questions: {len(questions)} au lieu de {expected_nb}")

    for i, q in enumerate(questions):
        if "enonce" not in q:
            errors.append(f"Question {i}: champ 'enonce' manquant")
        if "bonne_reponse" not in q:
            errors.append(f"Question {i}: champ 'bonne_reponse' manquant")
        if "explication" not in q:
            errors.append(f"Question {i}: champ 'explication' manquant")

        # Pour QCM/QRO, vérifier les options
        if type_quiz in ("qcm", "qro") and "options" not in q:
            errors.append(f"Question {i}: champ 'options' manquant pour {type_quiz}")
        elif type_quiz in ("qcm", "qro") and not isinstance(q.get("options"), list):
            errors.append(f"Question {i}: 'options' doit être une liste")

    return len(errors) == 0, errors
