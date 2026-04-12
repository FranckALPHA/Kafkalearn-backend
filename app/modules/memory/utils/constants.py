ITEM_TYPES = ["flashcard", "qcm", "cloze", "short_answer"]
ITEM_TYPES_CONFIG = {
    "flashcard": {"nb_default": 3, "description": "Recto/Verso"},
    "qcm": {"nb_default": 4, "description": "QCM"},
    "cloze": {"nb_default": 2, "description": "Phrase à trous"},
    "short_answer": {"nb_default": 2, "description": "Réponse courte"},
}
SM2_EF_MIN = 1.3
SM2_EF_START = 2.5
SM2_INITIAL_INTERVAL = 1
SM2_SECOND_INTERVAL = 6
MIN_REVIEW_SECONDS = 5
GRACE_HOURS = 24
ITEMS_PER_SECTION = 11  # Total default items per section
