"""
utils/math_evaluator.py
=======================
Évaluation sécurisée d'expressions mathématiques.
"""
import logging
import re

logger = logging.getLogger(__name__)


def evaluate_expression(expression: str) -> float:
    """
    Évalue une expression mathématique de manière sécurisée.
    Supporte: +, -, *, /, **, sqrt, sin, cos, tan, pi, e
    """
    # Nettoyage
    expression = expression.strip().replace(" ", "")

    # Whitelist des caractères autorisés
    allowed = set("0123456789+-*/.()sqrtincoap")
    if not all(c.lower() in allowed for c in expression):
        raise ValueError(f"Expression non autorisée: {expression}")

    # Remplacements sécurisés
    expression = expression.replace("sqrt", "math.sqrt")
    expression = expression.replace("sin", "math.sin")
    expression = expression.replace("cos", "math.cos")
    expression = expression.replace("tan", "math.tan")
    expression = expression.replace("pi", "math.pi")
    expression = expression.replace("e", "math.e")

    import math
    try:
        result = eval(expression, {"math": math, "__builtins__": {}}, {})
        return float(result)
    except Exception as e:
        logger.error(f"Math evaluation error: {e}")
        raise ValueError(f"Impossible d'évaluer: {expression}")


def check_math_answer(user_answer: str, correct_answer: float, tolerance: float = 0.01) -> bool:
    """Vérifie si la réponse de l'utilisateur est correcte."""
    try:
        user_val = float(user_answer.strip().replace(" ", ""))
        return abs(user_val - correct_answer) <= tolerance
    except (ValueError, TypeError):
        return False
