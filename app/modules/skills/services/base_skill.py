"""
services/base_skill.py
======================
Classe abstraite commune à tous les skills.
"""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

from pydantic import BaseModel

from app.modules.skills.utils.llm_client import LLMClient
from app.modules.search.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)

class SkillRequest(BaseModel):
    """Requête standardisée pour l'exécution d'un skill."""
    user_id: str
    prompt: str
    chat_session_id: Optional[str] = None
    langue: str = 'fr'
    params: Dict[str, Any] = {}
    avec_rag: bool = True
    user_document_id: Optional[int] = None
    historique_session: List[Dict[str, str]] = []  # derniers messages
    
class SkillResult(BaseModel):
    """Résultat standardisé d'un skill."""
    success: bool
    skill_type: str
    output_type: str  # 'text', 'pdf', 'json', 'png'
    data: Optional[Dict[str, Any]] = None  # métadonnées
    file_url: Optional[str] = None  # pour pdf/png
    json_data: Optional[Dict[str, Any]] = None  # pour json
    quota_consomme: bool = True
    latence_ms: Optional[int] = None
    rag_chunks_utilises: int = 0
    erreur_code: Optional[str] = None

class BaseSkill(ABC):
    """
    Contrat commun à tous les skills.
    Fournit les utilitaires partagés : LLM, RAG, logging.
    """
    
    def __init__(self, db, redis, llm_client: LLMClient):
        self.db = db
        self.redis = redis
        self.llm_client = llm_client
        self.search_orchestrator = SearchOrchestrator(db, redis)
    
    @abstractmethod
    async def run(self, request: SkillRequest) -> SkillResult:
        """
        Exécute le skill et retourne le résultat.
        À implémenter par chaque skill concret.
        """
        pass
    
    async def llm_generer(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.5,
        historique: List[Dict[str, str]] = None,
        langue: str = 'fr',
        response_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Wrapper unifié pour tous les appels LLM des skills.
        """
        # Construction des messages avec historique
        messages = []
        for msg in (historique or [])[-10:]:  # max 10 derniers
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})
        
        # Adaptation du system prompt à la langue
        if langue == 'fr':
            system_instruction = f"[FR] {system_instruction}\nRéponds en français."
        else:
            system_instruction = f"[EN] {system_instruction}\nRespond in English."
        
        return await self.llm_client.generate(
            messages=messages,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=4000,
            response_format=response_format
        )
    
    async def charger_contexte_rag(
        self,
        prompt: str,
        matiere: Optional[str] = None,
        niveau: Optional[str] = None,
        user_document_id: Optional[int] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Charge le contexte RAG pertinent pour enrichir le prompt LLM.
        """
        if not prompt.strip():
            return []
        
        try:
            result = await self.search_orchestrator.recherche_hybride(
                texte=prompt,
                filtres={"matiere": matiere, "niveau": niveau},
                top_k=top_k,
                source_module='skills'  # ← important: pas de logging search_logs
            )
            
            chunks = result.get("chunks", [])
            
            # Si document personnel spécifié, priorité à ses chunks
            if user_document_id:
                doc_chunks = [c for c in chunks if c.get("document_id") == user_document_id]
                if doc_chunks:
                    return doc_chunks[:top_k]
            
            return chunks
            
        except Exception as e:
            logger.warning(f"RAG context loading failed: {e}")
            return []  # Fallback: exécution sans contexte
    
    def formater_chunks_pour_prompt(self, chunks: List[Dict]) -> str:
        """
        Formate une liste de chunks pour injection dans le prompt LLM.
        """
        if not chunks:
            return ""
        
        formatted = "## Contexte documentaire pertinent:\n\n"
        for i, chunk in enumerate(chunks, 1):
            formatted += f"[Source {i}] {chunk.get('document_nom', 'Inconnu')} ({chunk.get('annee', '?')})\n"
            formatted += f"{chunk.get('texte_chunk', '')[:500]}...\n\n"
        
        return formatted.strip()