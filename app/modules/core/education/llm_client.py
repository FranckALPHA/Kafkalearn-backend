"""
app/modules/core/education/llm_client.py
=========================================
Client LLM pour l'extraction de métadonnées éducatives.
Utilise Ollama (phi3:mini) par défaut, fallback rule-based.
"""
import json
import logging
import re
import asyncio

logger = logging.getLogger(__name__)

# Sujets Cameroun — enrichis
MATIERES = {
    # Mathématiques
    "maths": "Mathematiques", "mathématique": "Mathematiques", "mathematique": "Mathematiques",
    "mathematiques": "Mathematiques", "math": "Mathematiques",
    # Physique
    "physique": "Physique", "phys": "Physique", "sci physique": "Physique",
    # Chimie
    "chimie": "Chimie",
    # SVT / SVTEEHB
    "svt": "SVTEEHB", "svteehb": "SVTEEHB", "svtee hb": "SVTEEHB",
    "sciences naturelles": "SVTEEHB", "biologie": "SVTEEHB",
    # Français
    "français": "Francais", "francais": "Francais", "littérature": "Francais",
    "litt": "Francais", "france": "Francais",
    # Anglais
    "anglais": "Anglais", "anglais": "Anglais", "english": "Anglais", "langue anglaise": "Anglais",
    # Allemand
    "allemand": "Allemand", "deutsch": "Allemand", "german": "Allemand",
    # Espagnol
    "espagnol": "Espagnol", "español": "Espagnol", "spanish": "Espagnol",
    # Histoire-Géographie
    "histoire": "Histoire-Geographie", "hist": "Histoire-Geographie",
    "geo": "Histoire-Geographie", "géographie": "Histoire-Geographie", "geographie": "Histoire-Geographie",
    "hist geo": "Histoire-Geographie", "histoire geographie": "Histoire-Geographie",
    # Philosophie
    "philosophie": "Philosophie", "philo": "Philosophie",
    # Informatique
    "informatique": "Informatique", "info": "Informatique", "tic": "Informatique",
    "ntic": "Informatique", "programmation": "Informatique",
    # ECM / EDM (Éducation civique)
    "ecm": "ECM", "edm": "ECM", "edu civique": "ECM", "education civique": "ECM",
    # PCT
    "pct": "PCT", "sciences physiques": "PCT",
    # Économie
    "economie": "Economie", "eco": "Economie",
    # Droit
    "droit": "Droit", "juridique": "Droit",
    # Comptabilité
    "comptabilite": "Comptabilite", "compta": "Comptabilite", "gestion": "Comptabilite",
    # EPS
    "eps": "EPS", "sport": "EPS", "education physique": "EPS",
    # Arts
    "arts plastiques": "Arts", "arts": "Arts", "musique": "Arts", "dessin": "Arts",
}

NIVEAUX = {
    "terminale": "Terminale", "tle": "Terminale", "tlecd": "Terminale CD",
    "premiere": "Premiere", "1ere": "Premiere", "1ère": "Premiere",
    "seconde": "Seconde", "2nde": "Seconde", "2eme": "Seconde",
    "3eme": "3eme", "3ème": "3eme",
    "4eme": "4eme", "4ème": "4eme",
    "5eme": "5eme", "5ème": "5eme",
    "6eme": "6eme", "6ème": "6eme",
    # Niveaux lycée technique
    "f4": "F4", "f3": "F3", "f2": "F2", "f1": "F1",
    # Probat / Bac
    "probatoire": "Probatoire", "prob": "Probatoire",
    "baccalaureat": "Baccalaureat", "bacc": "Baccalaureat", "bac": "Baccalaureat",
    # CEP / BEPC
    "cep": "CEP", "bepc": "BEPC",
    # Enseignement primaire
    "cm2": "CM2", "cm1": "CM1", "ce2": "CE2", "ce1": "CE1", "cp": "CP",
    # Maternelle
    "gs": "Grande Section", "ms": "Moyenne Section", "ps": "Petite Section",
}

SERIES = {
    "c": "C", "d": "D", "ti": "TI", "cd": "CD", "a": "A", "a4": "A4",
    "a1": "A1", "a2": "A2", "a3": "A3", "b": "B",
    "f4": "F4", "f3": "F3", "f2": "F2", "f1": "F1",
    "cde": "CDE", "tc": "TC", "td": "TD", "cg": "CG",
    "e4": "E4", "e3": "E3", "e2": "E2",
    "a4 all": "A4 All", "a4 esp": "A4 Esp",
}


def _detect_matiere(nom: str, texte: str) -> str:
    combo = f"{nom} {texte[:500]}".lower()
    # Tri par longueur décroissante pour matcher les clés les plus longues en premier
    for key, val in sorted(MATIERES.items(), key=lambda x: -len(x[0])):
        if key in combo:
            return val
    return "Autre"


def _detect_niveau(nom: str, texte: str) -> str:
    combo = f"{nom} {texte[:500]}".lower()
    for key, val in sorted(NIVEAUX.items(), key=lambda x: -len(x[0])):
        if re.search(r'\b' + re.escape(key) + r'\b', combo):
            return val
    return "Non specifie"


def _detect_serie(nom: str, texte: str) -> str:
    combo = f"{nom} {texte[:200]}".lower()
    for key, val in sorted(SERIES.items(), key=lambda x: -len(x[0])):
        if re.search(r'\b' + re.escape(key) + r'\b', combo):
            return val
    return None


def _detect_annee(nom: str) -> int:
    match = re.search(r'(20[0-2]\d)', nom)
    return int(match.group(1)) if match else 2026


def _detect_type_doc(nom: str, texte: str) -> str:
    combo = f"{nom} {texte[:300]}".lower()
    if any(k in combo for k in ["corrige", "correction", "solution", "corrigé"]):
        return "corrige"
    if any(k in combo for k in ["cours", "chapitre", "leçon", "resume", "résumé"]):
        return "cours"
    if any(k in combo for k in ["exercice", "td", "tp", "serie", "série", "travaux"]):
        return "exercice"
    if any(k in combo for k in ["eval", "examen", "devoir", "concours", "bacc", "bepc", "prob", "bac", "blanc", "epreuve"]):
        return "epreuve"
    return "epreuve"


def _detect_mots_cles(nom: str, texte: str) -> list:
    combo = f"{nom} {texte[:300]}".lower()
    mots = []
    keywords = [
        # Maths
        "integrale", "derivee", "fonction", "matrice", "suite", "probabilite",
        "equation", "inequation", "polynome", "geometrie", "trigonometrie",
        "logarithme", "exponentielle", "limite", "continuite", "derivee",
        # Physique
        "mecanique", "optique", "electricite", "thermodynamique", "onde",
        "cinematique", "newton", "energie", "pression", "courant", "tension",
        # Chimie
        "chimie organique", "reaction", "atome", "molecule", "oxydoreduction",
        "acide", "base", "solution", "concentration", "mole",
        # SVT
        "evolution", "cellule", "genetique", "reproduction", "digestion",
        "respiration", "photosynthese", "chromosome", "adn", "mutation",
        # Histoire-Géo
        "guerre", "colonisation", "independance", "democratie", "constitution",
        "mondialisation", "imperialisme", "decolonisation", "urbanisation",
        # Philosophie
        "conscience", "liberte", "verite", "justice", "bonheur", "devoir",
        "etat", "societe", "nature", "culture", "art", "travail",
        # Français
        "roman", "poesie", "theatre", "argumentation", "narration",
        "metaphore", "synecdoque", "hyperbole", "personnage",
        # Informatique
        "algorithme", "programmation", "base de donnees", "reseau", "web",
        "html", "python", "variable", "boucle", "fonction",
    ]
    for kw in keywords:
        if kw in combo:
            mots.append(kw)
    return mots[:5]


def _detect_sous_type(nom: str, texte: str) -> str:
    combo = f"{nom} {texte[:300]}".lower()
    if any(k in combo for k in ["zero", "epreuve zero", "sujet zero"]):
        return "epreuve_zero"
    if "blanc" in combo or "simili" in combo:
        return "examen_blanc"
    if "harmonise" in combo:
        return "examen_harmonise"
    if "national" in combo or "bacc" in combo or "bepc" in combo:
        return "examen_officiel"
    if "seq" in combo or "sequence" in combo:
        return "sequence"
    if "eval" in combo:
        return "evaluation"
    if "devoir" in combo:
        return "devoir"
    if "td" in combo:
        return "td"
    if "tp" in combo:
        return "tp"
    if "concours" in combo:
        return "concours"
    return None


def _detect_difficulte(nom: str, texte: str, niveau: str) -> str:
    combo = f"{nom} {texte[:300]}".lower()
    if any(k in combo for k in ["approfondi", "avance", "expert", "difficile"]):
        return "difficile"
    if any(k in combo for k in ["intro", "initiation", "base", "facile", "simple"]):
        return "facile"
    # Inferer du niveau
    if niveau in ["Terminale", "Baccalaureat"]:
        return "difficile"
    if niveau in ["Seconde", "3eme", "Premiere"]:
        return "moyen"
    if niveau in ["6eme", "5eme", "4eme"]:
        return "facile"
    return None


def _extract_via_ollama(nom: str, texte: str) -> dict:
    """Tente d'extraire les métadonnées via Ollama (phi3:mini)."""
    try:
        import httpx

        prompt = f"""Extract educational metadata from this document. Return ONLY valid JSON.
Document name: {nom}
Text excerpt: {texte[:2000]}

JSON fields: matiere, niveau, serie, type_doc, annee, sous_type, notion_principale, mots_cles, difficulte_estimee, langue"""

        with httpx.Client(timeout=60.0) as client:
            resp = client.post("http://localhost:11434/api/generate", json={
                "model": "qwen2.5:1.5b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 500},
            })
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "")
            # Extract JSON
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                metadata = json.loads(raw[start:end])
                logger.info("Ollama metadata extraction succeeded for %s", nom)
                return metadata
    except Exception as exc:
        logger.warning("Ollama metadata extraction failed for %s: %s", nom, exc)
    return {}


async def generate_text(prompt: str) -> str:
    """
    Generate metadata via Ollama (phi3:mini), fallback rule-based.
    Logs which provider is used.
    """
    try:
        # Extract document name from prompt
        nom_match = re.search(r"Document name:\s*(.+)", prompt)
        text_match = re.search(r"Text excerpt:\s*([\s\S]*?)\n\nExtract", prompt)

        nom = nom_match.group(1).strip() if nom_match else ""
        texte = text_match.group(1).strip()[:500] if text_match else ""

        # Try Ollama first
        ollama_meta = _extract_via_ollama(nom, texte)
        if ollama_meta and ollama_meta.get("matiere"):
            metadata = {
                "matiere": ollama_meta.get("matiere", _detect_matiere(nom, texte)),
                "niveau": ollama_meta.get("niveau", _detect_niveau(nom, texte)),
                "type_doc": ollama_meta.get("type_doc", _detect_type_doc(nom, texte)),
                "annee": ollama_meta.get("annee", _detect_annee(nom)),
                "serie": ollama_meta.get("serie") or _detect_serie(nom, texte),
                "sous_type": ollama_meta.get("sous_type") or _detect_sous_type(nom, texte),
                "notion_principale": ollama_meta.get("notion_principale"),
                "mots_cles": ollama_meta.get("mots_cles", []),
                "difficulte_estimee": ollama_meta.get("difficulte_estimee"),
                "langue": ollama_meta.get("langue", "fr"),
            }
            logger.info("LLM provider used: Ollama (qwen2.5:1.5b) for %s", nom)
            return json.dumps(metadata, ensure_ascii=False)

        # Fallback: rule-based
        logger.info("LLM provider used: Rule-based fallback for %s", nom)
        matiere = _detect_matiere(nom, texte)
        niveau = _detect_niveau(nom, texte)
        serie = _detect_serie(nom, texte)
        annee = _detect_annee(nom)
        type_doc = _detect_type_doc(nom, texte)
        sous_type = _detect_sous_type(nom, texte)
        difficulte = _detect_difficulte(nom, texte, niveau)
        mots_cles = _detect_mots_cles(nom, texte)

        metadata = {
            "matiere": matiere,
            "niveau": niveau,
            "type_doc": type_doc,
            "annee": annee,
            "serie": serie,
            "sous_type": sous_type,
            "notion_principale": mots_cles[0] if mots_cles else None,
            "mots_cles": mots_cles,
            "difficulte_estimee": difficulte,
            "langue": "fr",
        }

        return json.dumps(metadata, ensure_ascii=False)
    except Exception as exc:
        logger.error(f"Rule-based metadata generation failed: {exc}")
        return json.dumps({})
