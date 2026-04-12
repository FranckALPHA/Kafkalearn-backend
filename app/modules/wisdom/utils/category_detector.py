CATEGORY_KEYWORDS = {
    "humour": ["lion", "drôle", "rire", "absurde", "marrant", "funny", "laugh"],
    "strategie": ["stratégie", "plan", "méthode", "organiser", "strategy", "plan"],
    "etudes": ["réviser", "apprendre", "cours", "examen", "study", "learn", "exam"],
    "philosophie": ["vie", "avenir", "rêve", "succès", "life", "future", "dream"],
    "challenge": ["difficile", "effort", "courage", "persévérance", "hard", "effort"],
    "vigilance": ["attention", "piège", "erreur", "calculatrice", "careful", "mistake"],
}

def detect_category(text_fr: str, text_en: str) -> str:
    combined = f"{text_fr} {text_en}".lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in combined)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "vie"
