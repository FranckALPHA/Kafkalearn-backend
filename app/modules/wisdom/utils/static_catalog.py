import hashlib

WISDOM_TIPS_STATIC = [
    {"category": "etudes", "fr": {"text": "Un élève qui révise la veille du BAC est comme un cultivateur qui plante la veille de la récolte.", "author": "Proverbe camerounais revisité"}, "en": {"text": "A student who studies the night before the exam is like a farmer who plants the day before harvest.", "author": "Revisited Cameroonian proverb"}},
    {"category": "strategie", "fr": {"text": "Le Tle C qui maîtrise les intégrales n'a pas peur des questions bonus.", "author": "Sagesse de Mathématiques"}, "en": {"text": "The student who masters integrals has nothing to fear from bonus questions.", "author": "Mathematical Wisdom"}},
    {"category": "humour", "fr": {"text": "Apprends tes formules comme si un lion affamé lisait par-dessus ton épaule.", "author": "Le Mentor Absurde IA"}, "en": {"text": "Learn your formulas as if a hungry lion were reading over your shoulder.", "author": "The Absurd AI Mentor"}},
    {"category": "vigilance", "fr": {"text": "La calculatrice est ton amie, mais ta tête est ton meilleur outil.", "author": "Conseil de Physique"}, "en": {"text": "The calculator is your friend, but your brain is your best tool.", "author": "Physics Advice"}},
    {"category": "philosophie", "fr": {"text": "Chaque erreur est une pierre posée pour construire ta réussite future.", "author": "Philosophie de l'Effort"}, "en": {"text": "Every mistake is a stone laid to build your future success.", "author": "Philosophy of Effort"}},
    {"category": "challenge", "fr": {"text": "Ce qui semble impossible aujourd'hui sera ta force de demain.", "author": "Sagesse Africaine"}, "en": {"text": "What seems impossible today will be your strength tomorrow.", "author": "African Wisdom"}},
    {"category": "vie", "fr": {"text": "Le succès n'est pas la clé du bonheur. Le bonheur est la clé du succès.", "author": "Albert Schweitzer"}, "en": {"text": "Success is not the key to happiness. Happiness is the key to success.", "author": "Albert Schweitzer"}},
    {"category": "etudes", "fr": {"text": "La régularité bat l'intensité. Mieux vaut 30 min par jour que 5h le week-end.", "author": "Coach d'Études"}, "en": {"text": "Consistency beats intensity. Better 30 min daily than 5h on weekends.", "author": "Study Coach"}},
    {"category": "humour", "fr": {"text": "Si tu ne comprends pas les probas, la proba que tu rates le BAC augmente.", "author": "Statistiques Vraies"}, "en": {"text": "If you don't understand probability, the probability of failing the exam increases.", "author": "True Statistics"}},
    {"category": "strategie", "fr": {"text": "Commence par les questions faciles. Gagne des points, gagne confiance.", "author": "Stratégie d'Examen"}, "en": {"text": "Start with easy questions. Earn points, earn confidence.", "author": "Exam Strategy"}},
]


def get_static_tip_by_date(date_obj) -> dict:
    import hashlib
    date_str = date_obj.isoformat()
    hash_val = int(hashlib.md5(date_str.encode()).hexdigest(), 16)
    index = hash_val % len(WISDOM_TIPS_STATIC)
    return WISDOM_TIPS_STATIC[index]
