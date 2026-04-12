class PromptBuilder:
    @classmethod
    def build_system_prompt(cls, analysis_type: str, langue: str) -> str:
        if analysis_type == "epreuve":
            return cls._system_epreuve(langue)
        return cls._system_lecon(langue)

    @classmethod
    def _system_epreuve(cls, langue: str) -> str:
        base = """Tu es un expert pédagogique camerounais. Analyse l'épreuve fournie et retourne UNIQUEMENT un JSON valide:
{"key_points": [...], "concepts": [...], "tips": [...], "methodologie": "...", "notions_prerequis": [...], "difficulte_detail": {}}
Règles: JSON uniquement, langue {langue}, concret, basé UNIQUEMENT sur le contenu fourni."""
        return base.format(langue=langue)

    @classmethod
    def _system_lecon(cls, langue: str) -> str:
        base = """Tu es un expert pédagogique camerounais. Analyse la leçon fournie et retourne UNIQUEMENT un JSON valide:
{"summary": "...", "concepts": [...], "key_points": [...], "tips": [...], "notions_prerequis": [...]}
Règles: JSON uniquement, langue {langue}, summary narratif, tips actionnables."""
        return base.format(langue=langue)

    @classmethod
    def build_user_prompt(cls, document: dict) -> str:
        metadata = f"Matière: {document.get('matiere', '?')}\nNiveau: {document.get('niveau', '?')}\nSérie: {document.get('serie', '?')}"
        content = document.get('texte_extrait', '')[:2000]
        return f"{metadata}\n\nContenu:\n{content}"
