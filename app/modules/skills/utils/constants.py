"""
utils/constants.py
==================
Patterns d'intention, catalogues de skills, mapping de plans.
"""

# ─── Skill Intent Patterns ──────────────────────────────────────
PATTERNS_INTENT = {
    "fiche": [
        r"\b(fiche|résum|synth[èe]se|apprendre|m[ée]moriser|r[ée]viser)\b",
        r"\b(cours|le[cç]on|notions?|d[ée]finition|formule)\b",
    ],
    "quiz": [
        r"\b(quiz|qcm|exercices?\s*(de|sur)|tester|évaluer|evaluer)\b",
        r"\b(question[s]?|probl[èe]me[s]?|interro[gation]?)\b",
    ],
    "solver": [
        r"\b(r[ée]soudre?|calculer|trouver|x\s*=|équation|[ée]quation)\b",
        r"\b(d[ée]montrer?|prouver?|montrer que|combien)\b",
    ],
    "tuteur": [
        r"\b(explique|comprendre|comment|pourquoi|qu'est-ce que)\b",
        r"\b(aide|aider|aider-moi|je comprends pas|c'est quoi)\b",
    ],
    "corrige": [
        r"\b(corrig[ée]|solution|correction|r[ée]ponse[s]?)\b",
    ],
    "epreuve": [
        r"\b([ée]preuve|examen|contr[oô]le|devoir|sujet)\b",
        r"\b(cr[ée]er|g[ée]n[ée]rer|produire|inventer).*(sujet|[ée]preuve)\b",
    ],
    "visualisation": [
        r"\b(graphe|diagramme|sch[ée]ma|courbe|graphique|tracer)\b",
        r"\b(visualiser|repr[ée]sentation|dessiner)\b",
    ],
}

# ─── Skill Catalog ──────────────────────────────────────────────
SKILL_CATALOG = {
    "fiche": {
        "nom": "Fiche de révision",
        "description": "Génère une fiche de révision structurée avec résumé, méthodes et exemples",
        "output_type": "text",
        "plan_requis": "access",
        "exemple_prompt": "Fiche de révision sur les dérivées en Mathématiques Terminale C",
    },
    "quiz": {
        "nom": "Quiz interactif",
        "description": "Génère un quiz QCM/QRO avec correction automatique et feedback",
        "output_type": "json",
        "plan_requis": "access",
        "exemple_prompt": "Quiz de 10 questions sur la Révolution française en Histoire",
    },
    "solver": {
        "nom": "Résolveur",
        "description": "Résout un problème pas-à-pas avec explications détaillées",
        "output_type": "text",
        "plan_requis": "access",
        "exemple_prompt": "Résous x² + 3x - 4 = 0 en expliquant chaque étape",
    },
    "tuteur": {
        "nom": "Tuteur IA",
        "description": "Agent conversationnel pédagogique pour expliquer et guider",
        "output_type": "text",
        "plan_requis": "freemium",
        "exemple_prompt": "Explique-moi le théorème de Pythagore simplement",
    },
    "corrige": {
        "nom": "Corrigé d'épreuve",
        "description": "Génère un corrigé détaillé avec barème pour une épreuve existante",
        "output_type": "text",
        "plan_requis": "access",
        "exemple_prompt": "Corrigé de l'épreuve de Mathématiques BAC 2024 Série C",
    },
    "epreuve": {
        "nom": "Générateur d'épreuves",
        "description": "Crée des sujets d'examen originaux conformes au programme",
        "output_type": "text",
        "plan_requis": "pro",
        "exemple_prompt": "Crée une épreuve de Physique Terminale D, durée 3h, coef 4",
    },
    "visualisation": {
        "nom": "Visualisation",
        "description": "Génère des descriptions de graphes, diagrammes et schémas",
        "output_type": "text",
        "plan_requis": "pro",
        "exemple_prompt": "Trace la courbe de f(x) = x³ - 3x + 2",
    },
}

# ─── Plan Hierarchy ─────────────────────────────────────────────
PLAN_HIERARCHY = ["freemium", "access", "premium", "pro", "unlimited", "school"]

PLAN_REQUIREMENTS = {
    "fiche": "access",
    "quiz": "access",
    "solver": "access",
    "tuteur": "freemium",
    "corrige": "access",
    "epreuve": "pro",
    "visualisation": "pro",
}
