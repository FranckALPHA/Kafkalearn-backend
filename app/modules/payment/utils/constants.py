PLANS = ["freemium", "access", "premium", "pro", "unlimited", "school"]
PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited", "school"]
PAYMENT_CHANNELS = ["cm.mtn", "cm.orange", "cm.orange_money", "cm.mtn_momo"]

PLAN_FEATURES = {
    "freemium": ["Consultation des epreuves", "5 requetes IA/mois"],
    "access": ["+ Telechargement PDF", "5 requetes IA/mois"],
    "premium": ["+ Recherche semantique avancee", "10 requetes IA/jour"],
    "pro": ["+ Skills IA (fiches, quiz...)", "25 requetes IA/jour", "Playlists illimitees"],
    "unlimited": ["Acces complet", "200 requetes IA/jour (soft cap)"],
    "school": ["Acces Pro pour tous les membres", "Tableau de bord ecole"],
}

DEFAULT_PRICES = {
    "access": 500,
    "premium": 1500,
    "pro": 3000,
    "unlimited": 8000,
    "school": 0,  # Pricing per seat
}

SCHOOL_PRICE_PER_SEAT = {
    (1, 50): 250,
    (51, 200): 200,
    (201, 500): 150,
    (501, None): 100,  # Custom pricing
}
