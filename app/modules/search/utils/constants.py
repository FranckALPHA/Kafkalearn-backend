"""
utils/constants.py
==================
Mots-clés d'intention, mapping matières, stopwords.
"""

# ─── Intention detection keywords ───────────────────────────────
MOTS_INTENTION_EXPLICATION = [
    "explique", "cours", "leçon", "définition", "comprendre",
    "comment", "pourquoi", "qu'est-ce que", "definir", "resumer",
    "resume", "c'est quoi", "definition", "expliquer",
]

MOTS_INTENTION_ENTRAINEMENT = [
    "exercice", "probleme", "examen", "epreuve", "corriger",
    "résoudre", "resoudre", "calculer", "trouver", "demontrer",
    "démontrer", "quiz", "td", "tp", "devoir",
]

# ─── Subject mapping ────────────────────────────────────────────
MATIERES_MAPPING = {
    "math": "Mathématiques", "maths": "Mathématiques", "mathematiques": "Mathématiques",
    "physique": "Physique", "phy": "Physique",
    "chimie": "Chimie", "chi": "Chimie",
    "svt": "SVT", "bio": "SVT", "biologie": "SVT",
    "francais": "Français", "fr": "Français",
    "anglais": "Anglais", "en": "Anglais",
    "philosophie": "Philosophie", "philo": "Philosophie",
    "histoire": "Histoire-Géographie", "hist": "Histoire-Géographie", "geo": "Histoire-Géographie",
    "info": "Informatique", "informatique": "Informatique",
}

# ─── French stopwords ───────────────────────────────────────────
STOPWORDS_FR = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou",
    "mais", "donc", "car", "que", "qui", "dans", "sur", "sous",
    "avec", "sans", "pour", "par", "en", "a", "est", "sont", "je",
    "tu", "il", "elle", "nous", "vous", "ils", "elles", "ce", "c",
    "se", "me", "te", "y", "ne", "pas", "plus", "moins", "tres",
    "au", "aux", "leur", "leurs", "son", "sa", "ses", "mon", "ton",
}

# ─── Vespa field mapping ────────────────────────────────────────
VESPA_FIELD_MAP = {
    "matiere": "matiere",
    "niveau": "niveau",
    "serie": "serie",
    "annee": "annee",
    "type_doc": "type_document",
}
