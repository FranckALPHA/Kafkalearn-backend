"""
utils/i18n.py
=============
Système centralisé de gestion bilingue FR/EN pour tous les prompts LLM
et messages utilisateur de KafkaLearn.
"""
from typing import Dict, Any

# ─── Language map ──────────────────────────────────────────────────

LANG_NAMES = {"fr": "Français", "en": "English"}

# ─── Search Responder prompts ──────────────────────────────────────

SEARCH_RESPONDER_SYSTEM = {
    "fr": (
        "Tu es un assistant pédagogique expert pour les élèves camerounais. "
        "Réponds de manière claire, structurée et pédagogique. "
        "Utilise des exemples concrets adaptés au contexte camerounais. "
        "Si la question porte sur un exercice, explique la méthodologie étape par étape."
    ),
    "en": (
        "You are a pedagogical assistant expert for Cameroonian students. "
        "Respond clearly, in a structured and pedagogical manner. "
        "Use concrete examples adapted to the Cameroonian context. "
        "If the question is about an exercise, explain the methodology step by step."
    ),
}

SEARCH_RESPONDER_USER_TEMPLATE = {
    "fr": (
        "Question : {query}\n\n"
        "Contexte (documents trouvés) :\n{context}\n\n"
        "Réponds en te basant sur le contexte fourni."
    ),
    "en": (
        "Question: {query}\n\n"
        "Context (documents found):\n{context}\n\n"
        "Answer based on the provided context."
    ),
}

# ─── Skill system prompts ──────────────────────────────────────────

SKILL_SYSTEM_PROMPTS = {
    "fiche": {
        "fr": (
            "Tu es un professeur expert. Génère une fiche de révision complète et structurée. "
            "Inclue : définitions, formules clés, exemples, pièges à éviter."
        ),
        "en": (
            "You are an expert teacher. Generate a complete and structured revision sheet. "
            "Include: definitions, key formulas, examples, common pitfalls."
        ),
    },
    "quiz": {
        "fr": (
            "Tu es un examinateur. Génère un quiz avec questions progressives (facile → difficile). "
            "Chaque question doit avoir 4 options, la bonne réponse et une explication détaillée."
        ),
        "en": (
            "You are an examiner. Generate a quiz with progressive questions (easy → hard). "
            "Each question must have 4 options, the correct answer, and a detailed explanation."
        ),
    },
    "solver": {
        "fr": (
            "Tu es un professeur de soutien. Résous l'exercice étape par étape en expliquant "
            "chaque raisonnement. Utilise un ton encourageant."
        ),
        "en": (
            "You are a tutoring teacher. Solve the exercise step by step, explaining each reasoning. "
            "Use an encouraging tone."
        ),
    },
    "corrige": {
        "fr": (
            "Tu es un correcteur d'examen. Corrige la réponse de l'élève en détaillant "
            "les erreurs et en donnant la réponse attendue avec explication."
        ),
        "en": (
            "You are an exam grader. Correct the student's answer, detailing errors "
            "and providing the expected answer with explanation."
        ),
    },
    "tuteur": {
        "fr": (
            "Tu es un tuteur patient. Explique le concept demandé comme si tu parlais "
            "à un élève qui découvre le sujet. Utilise des analogies concrètes."
        ),
        "en": (
            "You are a patient tutor. Explain the requested concept as if speaking "
            "to a student discovering the subject. Use concrete analogies."
        ),
    },
}

# ─── Coach IA messages ─────────────────────────────────────────────

COACH_MESSAGES = {
    "no_data": {
        "fr": "📚 Prêt pour une session de révision ?",
        "en": "📚 Ready for a study session?",
    },
    "lacune_detectee": {
        "fr": "Tu as des lacunes en {matiere}. Une fiche de révision t'aidera.",
        "en": "You have gaps in {matiere}. A revision sheet will help.",
    },
    "blocage_profond": {
        "fr": "Tu bloques sur {concept} depuis {weeks} semaines. Reprenons les bases.",
        "en": "You've been stuck on {concept} for {weeks} weeks. Let's go back to basics.",
    },
    "maitrise": {
        "fr": "Tu maîtrises {concept} ! Tu peux passer au niveau suivant.",
        "en": "You've mastered {concept}! You can move to the next level.",
    },
    "urgence_examen": {
        "fr": "🚀 Mode urgence ! {days} jours avant l'examen. On se concentre sur l'essentiel.",
        "en": "🚀 Emergency mode! {days} days before the exam. Let's focus on essentials.",
    },
    "streak": {
        "fr": "🔥 {days} jours de suite ! Impressionnant.",
        "en": "🔥 {days} days in a row! Impressive.",
    },
    "session_recommendation": {
        "fr": "Aujourd'hui : '{concept}' en {matiere}. Session d'environ {duration} min.",
        "en": "Today: '{concept}' in {matiere}. Session of about {duration} min.",
    },
}

# ─── Doc Analysis prompts ──────────────────────────────────────────

DOC_ANALYSIS_SYSTEM = {
    "fr": (
        "Tu es un expert pédagogique du système scolaire camerounais. "
        "Analyse ce document et retourne une analyse structurée en JSON."
    ),
    "en": (
        "You are a pedagogical expert in the Cameroonian school system. "
        "Analyze this document and return a structured analysis in JSON."
    ),
}

DOC_ANALYSIS_USER = {
    "fr": (
        "Document :\n"
        "Matière : {matiere}\n"
        "Niveau : {niveau}\n"
        "Série : {serie}\n\n"
        "Contenu :\n{texte_extrait}"
    ),
    "en": (
        "Document:\n"
        "Subject: {matiere}\n"
        "Level: {niveau}\n"
        "Track: {serie}\n\n"
        "Content:\n{texte_extrait}"
    ),
}

# ─── Helper functions ──────────────────────────────────────────────

def get_langue(user_or_str) -> str:
    """Extrait la langue d'un objet User ou d'une string. Fallback: 'fr'."""
    if isinstance(user_or_str, str):
        return user_or_str if user_or_str in ("fr", "en") else "fr"
    if hasattr(user_or_str, "langue") and user_or_str.langue:
        return user_or_str.langue if user_or_str.langue in ("fr", "en") else "fr"
    return "fr"


def t(dictionary: Dict[str, Any], langue: str, default_langue: str = "fr") -> str:
    """Traduit une clé selon la langue. Fallback: default_langue puis la clé elle-même."""
    if langue in dictionary:
        return dictionary[langue]
    if default_langue in dictionary:
        return dictionary[default_langue]
    return list(dictionary.values())[0] if dictionary else ""


def format_msg(template: str, **kwargs) -> str:
    """Formate un template avec les kwargs, en gérant les clés manquantes."""
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
