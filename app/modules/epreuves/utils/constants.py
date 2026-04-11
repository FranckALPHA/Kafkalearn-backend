"""
utils/constants.py
==================
Constantes pour le module epreuves : matières, niveaux, séries, régions.
"""

MATIERES = [
    "Mathématiques", "Physique", "Chimie", "SVT", "Français",
    "Anglais", "Philosophie", "Histoire-Géographie", "Informatique",
    "Économie", "Comptabilité", "Génie Civil", "Électrotechnique",
]

NIVEAUX = [
    "6ème", "5ème", "4ème", "3ème",
    "Seconde", "Première", "Terminale",
]

SERIES = [
    "A4", "A", "C", "D", "E", "F", "G", "TI", "TSE",
]

REGIONS = [
    "Adamaoua", "Centre", "Est", "Extrême-Nord", "Littoral",
    "Nord", "Nord-Ouest", "Ouest", "Sud", "Sud-Ouest",
]

TYPES_DOC = ["epreuve", "lecon"]

SOUS_TYPES = [
    "composition_1", "composition_2", "examen_blanc",
    "rattrapage", "concours", "cours", "td", "tp",
]

DIFFICULTES = ["facile", "moyen", "difficile"]

LANGUES = ["fr", "en", "both"]

INGEST_STATUSES = ["pending", "ocr_done", "embedded", "failed"]

MAX_FILE_SIZE_MB = 50

ALLOWED_MIMETYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]

ALLOWED_EXTENSIONS = [".pdf", ".docx"]
