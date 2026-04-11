from enum import Enum
from typing import Optional, List, Dict, Any
import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    GEMINI = "gemini"
    MISTRAL = "mistral"
    OPENROUTER = "openrouter"

class LLMClient:
    """
    Client LLM unifié avec fallback automatique et gestion des quotas.
    """
    
    def __init__(self, api_keys: Dict[str, str], default_provider: LLMProvider = LLMProvider.GEMINI):
        self.api_keys = api_keys
        self.default_provider = default_provider
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Endpoints par provider
        self.endpoints = {
            LLMProvider.GEMINI: "https://generativelanguage.googleapis.com/v1beta/models",
            LLMProvider.MISTRAL: "https://api.mistral.ai/v1/chat/completions",
            LLMProvider.OPENROUTER: "https://openrouter.ai/api/v1/chat/completions"
        }
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException))
    )
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_instruction: Optional[str] = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
        response_format: Optional[str] = None,  # 'json' pour forcer JSON
        provider: Optional[LLMProvider] = None
    ) -> Dict[str, Any]:
        """
        Génère une réponse via le provider spécifié (ou default).
        
        Returns:
            {
                "text": str,
                "tokens_used": int,
                "provider": str,
                "latency_ms": int,
                "error_code": Optional[str]
            }
        """
        provider = provider or self.default_provider
        start_ms = time.time() * 1000
        
        try:
            if provider == LLMProvider.GEMINI:
                result = await self._call_gemini(messages, system_instruction, temperature, max_tokens, response_format)
            elif provider == LLMProvider.MISTRAL:
                result = await self._call_mistral(messages, temperature, max_tokens, response_format)
            elif provider == LLMProvider.OPENROUTER:
                result = await self._call_openrouter(messages, temperature, max_tokens, response_format)
            else:
                raise ValueError(f"Provider inconnu: {provider}")
            
            latency_ms = int(time.time() * 1000 - start_ms)
            return {
                **result,
                "provider": provider.value,
                "latency_ms": latency_ms,
                "error_code": None
            }
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return {"error_code": "QUOTA_LLM", "provider": provider.value}
            elif e.response.status_code == 401:
                return {"error_code": "API_KEY_INVALID", "provider": provider.value}
            else:
                logger.error(f"LLM HTTP {e.response.status_code}: {e.response.text}")
                return {"error_code": "LLM_HTTP_ERROR", "provider": provider.value}
                
        except Exception as e:
            logger.error(f"LLM generation error: {e}", exc_info=True)
            return {"error_code": "LLM_ERROR", "provider": provider.value}
    
    async def _call_gemini(self, messages, system_instruction, temperature, max_tokens, response_format):
        """Appel API Gemini avec formatage spécifique."""
        # Construction du prompt selon le format Gemini
        contents = []
        if system_instruction:
            contents.append({"role": "system", "parts": [{"text": system_instruction}]})
        
        for msg in messages:
            contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        
        if response_format == "json":
            payload["generationConfig"]["response_mime_type"] = "application/json"
        
        model_name = "gemini-1.5-flash"  # ou configurable
        url = f"{self.endpoints[LLMProvider.GEMINI]}/{model_name}:generateContent?key={self.api_keys['gemini']}"
        
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        
        return {"text": text, "tokens_used": tokens}
    
    # _call_mistral et _call_openrouter suivent le même pattern...
    
    async def close(self):
        await self.client.aclose()