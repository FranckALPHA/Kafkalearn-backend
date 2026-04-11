"""
modules/core/education/helpers.py
=================================
Normalisation des données éducatives.
"""


def normalize_matiere(value: str) -> str:
    """Normalise un nom de matière."""
    mapping = {
        "math": "Mathématiques", "maths": "Mathématiques", "mathematiques": "Mathématiques",
        "physique": "Physique", "phy": "Physique",
        "svt": "SVT", "bio": "SVT",
        "francais": "Français", "fr": "Français",
        "anglais": "Anglais", "en": "Anglais",
        "philo": "Philosophie", "philosophie": "Philosophie",
        "histoire": "Histoire-Géographie", "hist": "Histoire-Géographie", "geo": "Histoire-Géographie",
        "info": "Informatique", "informatique": "Informatique",
    }
    return mapping.get(value.lower().strip(), value.strip().title())


def normalize_niveau(value: str) -> str:
    """Normalise un niveau."""
    mapping = {
        "tle": "Terminale", "terminale": "Terminale",
        "1ere": "Première", "premiere": "Première", "première": "Première",
        "2nde": "Seconde", "seconde": "Seconde",
        "3eme": "3ème", "troisieme": "3ème", "troisième": "3ème",
    }
    return mapping.get(value.lower().strip(), value.strip())
