class PromptTemplates:
    BASE_SYSTEM = """Tu es un expert en pédagogie et mémorisation active. Génère des items de révision basés UNIQUEMENT sur le texte fourni. Réponds UNIQUEMENT en JSON valide."""

    @classmethod
    def for_qcm(cls, nb: int, langue: str, niveau: str) -> str:
        return f"""{cls.BASE_SYSTEM}
Génère EXACTEMENT {nb} questions QCM. Niveau: {niveau}. Langue: {langue}.
Format: [{{"question": "...", "options": ["A","B","C","D"], "bonne_reponse": "...", "explication": "..."}}]
Texte: {{texte_section}}"""

    @classmethod
    def for_flashcard(cls, nb: int, langue: str, niveau: str) -> str:
        return f"""{cls.BASE_SYSTEM}
Génère EXACTEMENT {nb} flashcards. Niveau: {niveau}. Langue: {langue}.
Format: [{{"recto": "...", "verso": "..."}}]
Texte: {{texte_section}}"""

    @classmethod
    def for_cloze(cls, nb: int, langue: str, niveau: str) -> str:
        return f"""{cls.BASE_SYSTEM}
Génère EXACTEMENT {nb} phrases à trous. Niveau: {niveau}. Langue: {langue}.
Format: [{{"enonce": "Phrase avec ___", "alternatives": "rep1|rep2", "explication": "..."}}]
Texte: {{texte_section}}"""

    @classmethod
    def for_short_answer(cls, nb: int, langue: str, niveau: str) -> str:
        return f"""{cls.BASE_SYSTEM}
Génère EXACTEMENT {nb} questions réponse courte. Niveau: {niveau}. Langue: {langue}.
Format: [{{"question": "...", "bonne_reponse": "...", "explication": "..."}}]
Texte: {{texte_section}}"""
