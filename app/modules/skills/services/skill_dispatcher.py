"""
services/skill_dispatcher.py
============================
Détection d'intention + routage vers le skill approprié.
"""
import logging
import re
import time
from typing import Optional, Tuple

from fastapi import HTTPException

from app.modules.skills.services.base import SkillsBaseService
from app.modules.skills.services.base_skill import BaseSkill
from app.modules.skills.services.fiche_skill import FicheSkill
from app.modules.skills.services.quiz_skill import QuizSkill
from app.modules.skills.services.solver_skill import SolverSkill
from app.modules.skills.services.tuteur_skill import TuteurSkill
from app.modules.skills.services.corrige_skill import CorrigeSkill
from app.modules.skills.services.epreuve_skill import EpreuveSkill
from app.modules.skills.services.visualisation_skill import VisualisationSkill
from app.modules.skills.utils.constants import PATTERNS_INTENT
from app.modules.skills.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

class SkillDispatcher(SkillsBaseService):
    """
    Détecte l'intention de l'utilisateur et route vers le skill approprié.
    """

    SKILL_MAP = {
        "fiche": FicheSkill,
        "quiz": QuizSkill,
        "solver": SolverSkill,
        "tuteur": TuteurSkill,
        "corrige": CorrigeSkill,
        "epreuve": EpreuveSkill,
        "visualisation": VisualisationSkill,
    }
    
    def __init__(self, db, redis=None, llm_client: LLMClient = None):
        super().__init__(db, redis)
        self.llm_client = llm_client or LLMClient(api_keys={})
    
    async def dispatch(
        self,
        prompt: str,
        skill_explicite: Optional[str] = None,
        user_params: dict = None,
        user_plan: str = 'freemium'
    ) -> tuple[BaseSkill, str, str]:
        """
        Route la requête vers le skill approprié.
        
        Returns:
            (skill_instance, skill_type, detection_method)
            detection_method ∈ {'explicit', 'regex', 'llm', 'fallback'}
        """
        # ─── Cas 1: Skill explicite fourni ───────────────────────
        if skill_explicite:
            if skill_explicite not in self.SKILL_MAP:
                raise ValueError(f"Skill inconnu: {skill_explicite}")
            
            skill_class = self.SKILL_MAP[skill_explicite]
            self._verify_plan_access(skill_explicite, user_plan)
            
            return skill_class(self.db, self.redis, self.llm_client), skill_explicite, 'explicit'
        
        # ─── Cas 2: Détection par regex (rapide) ─────────────────
        detected_skill, method = self._detecter_regex(prompt)
        if detected_skill:
            self._verify_plan_access(detected_skill, user_plan)
            skill_class = self.SKILL_MAP[detected_skill]
            return skill_class(self.db, self.redis, self.llm_client), detected_skill, 'regex'
        
        # ─── Cas 3: Détection par LLM (plus précis, plus lent) ───
        detected_skill = await self._classifier_llm(prompt)
        if detected_skill:
            self._verify_plan_access(detected_skill, user_plan)
            skill_class = self.SKILL_MAP[detected_skill]
            return skill_class(self.db, self.redis, self.llm_client), detected_skill, 'llm'
        
        # ─── Fallback: Tuteur universel ──────────────────────────
        return TuteurSkill(self.db, self.redis, self.llm_client), 'tuteur', 'fallback'
    
    def _detecter_regex(self, texte: str) -> tuple[Optional[str], str]:
        """
        Détection rapide par patterns regex.
        
        Returns:
            (skill_type or None, 'regex' or None)
        """
        texte_lower = texte.lower()
        
        for skill_type, patterns in PATTERNS_INTENT.items():
            if any(re.search(pattern, texte_lower) for pattern in patterns):
                return skill_type, 'regex'
        
        return None, None
    
    async def _classifier_llm(self, texte: str) -> Optional[str]:
        """
        Classification d'intention via LLM léger.
        """
        system_prompt = """
        Tu es un classificateur d'intentions pédagogiques.
        Catégories disponibles: fiche, quiz, solver, tuteur, corrige, epreuve, visualisation
        
        Règles:
        - "fiche" = révision, synthèse, résumé, apprendre
        - "quiz" = tester, questions, QCM, évaluer, exercices
        - "solver" = résoudre, calculer, trouver x, équation
        - "tuteur" = expliquer, comprendre, aide, question ouverte
        - "corrige" = correction, solution, corrigé d'un exercice
        - "epreuve" = créer un sujet, examen, contrôle
        - "visualisation" = graphe, diagramme, schéma, courbe
        
        Réponds UNIQUEMENT par le nom du skill, rien d'autre.
        """
        
        result = await self.llm_client.generate(
            messages=[{"role": "user", "content": f"Intention: {texte}"}],
            system_instruction=system_prompt,
            temperature=0.1,  # Très déterministe
            max_tokens=20
        )
        
        if result.get("error_code"):
            return None
        
        skill_detected = result["text"].strip().lower()
        return skill_detected if skill_detected in self.SKILL_MAP else None
    
    def _verify_plan_access(self, skill_type: str, user_plan: str) -> bool:
        """
        Vérifie que le plan utilisateur permet d'accéder au skill.
        
        NOTE: Disabled for development phase - all skills accessible.
        """
        # DEV MODE: Skip plan checks
        return True
        
        PLAN_REQUIREMENTS = {
            'fiche': 'access',
            'quiz': 'access',
            'solver': 'access',
            'tuteur': 'freemium',  # Toujours accessible
            'corrige': 'access',
            'epreuve': 'pro',
            'visualisation': 'pro'
        }

        PLAN_HIERARCHY = ['freemium', 'access', 'premium', 'pro', 'unlimited', 'school']

        required = PLAN_REQUIREMENTS.get(skill_type, 'freemium')
        user_level = PLAN_HIERARCHY.index(user_plan) if user_plan in PLAN_HIERARCHY else 0
        required_level = PLAN_HIERARCHY.index(required) if required in PLAN_HIERARCHY else 0

        if user_level < required_level:
            from fastapi import HTTPException
            raise HTTPException(403, "PLAN_INSUFFISANT")

        return True
    
    async def extraire_params_llm(self, texte: str, skill_type: str, user_profile: dict) -> dict:
        """
        Extrait les paramètres pédagogiques via LLM.
        
        Returns:
            Dict de paramètres enrichis: {matiere, niveau, serie, nb_questions, notion...}
        """
        system_prompt = f"""
        Tu extrais les paramètres pédagogiques d'une demande de skill "{skill_type}".
        
        Paramètres à extraire (JSON):
        - matiere: str (ex: "Mathématiques", "Physique")
        - niveau: str (ex: "Tle", "3ème", "Form 5")
        - serie: str (ex: "C", "D", "A4")
        - notion: str (le sujet précis)
        - nb_questions: int (pour quiz, max 20)
        - difficulte: str (facile|moyen|difficile)
        - nb_pages: int (pour fiche, 1-5)
        
        Réponds UNIQUEMENT en JSON valide, sans texte autour.
        Utilise null pour les paramètres non détectés.
        """
        
        context = f"Profil utilisateur: classe={user_profile.get('classe')}, serie={user_profile.get('serie')}, langue={user_profile.get('langue')}"
        
        result = await self.llm_client.generate(
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": f"Demande: {texte}"}
            ],
            system_instruction=system_prompt,
            temperature=0.2,
            max_tokens=300,
            response_format="json"
        )
        
        if result.get("error_code"):
            return {}
        
        try:
            import json
            params = json.loads(result["text"])
            # Fusion avec valeurs par défaut du profil
            return {k: v for k, v in params.items() if v is not None}
        except:
            return {}