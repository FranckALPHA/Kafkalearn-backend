"""
utils/prompt_builder.py
=======================
Prompts bilingues FR/EN pour l'analyse de documents.
"""
from app.core.utils.i18n import t

PROMPTS = {
    "system_epreuve": {
        "fr": (
            "Tu es un expert pédagogique camerounais. Analyse l'épreuve fournie et retourne UNIQUEMENT un JSON valide :\n"
            '{{"key_points": [...], "concepts": [...], "tips": [...], "methodologie": "...", "notions_prerequis": [...], "difficulte_detail": {{}}}}\n'
            "Règles : JSON uniquement, concret, basé UNIQUEMENT sur le contenu fourni."
        ),
        "en": (
            "You are a Cameroonian pedagogical expert. Analyze the provided exam and return ONLY valid JSON:\n"
            '{{"key_points": [...], "concepts": [...], "tips": [...], "methodology": "...", "prerequisite_notions": [...], "difficulty_detail": {{}}}}\n'
            "Rules: JSON only, concrete, based ONLY on the provided content."
        ),
    },
    "system_lecon": {
        "fr": (
            "Tu es un expert pédagogique camerounais. Analyse la leçon fournie et retourne UNIQUEMENT un JSON valide :\n"
            '{{"summary": "...", "concepts": [...], "key_points": [...], "tips": [...], "notions_prerequis": [...]}}\n'
            "Règles : JSON uniquement, summary narratif, tips actionnables."
        ),
        "en": (
            "You are a Cameroonian pedagogical expert. Analyze the provided lesson and return ONLY valid JSON:\n"
            '{{"summary": "...", "concepts": [...], "key_points": [...], "tips": [...], "prerequisite_notions": [...]}}\n'
            "Rules: JSON only, narrative summary, actionable tips."
        ),
    },
    "user_prompt": {
        "fr": "Matière: {matiere}\nNiveau: {niveau}\nSérie: {serie}\n\nContenu:\n{texte_extrait}",
        "en": "Subject: {matiere}\nLevel: {niveau}\nTrack: {serie}\n\nContent:\n{texte_extrait}",
    },
}


class PromptBuilder:
    @classmethod
    def build_system_prompt(cls, analysis_type: str, langue: str) -> str:
        if analysis_type == "epreuve":
            return t(PROMPTS["system_epreuve"], langue)
        return t(PROMPTS["system_lecon"], langue)

    @classmethod
    def build_user_prompt(cls, document: dict) -> str:
        from app.core.utils.i18n import format_msg
        return format_msg(
            t(PROMPTS["user_prompt"], document.get("langue", "fr")),
            matiere=document.get("matiere", "?"),
            niveau=document.get("niveau", "?"),
            serie=document.get("serie", "?"),
            texte_extrait=document.get("texte_extrait", "")[:2000],
        )
