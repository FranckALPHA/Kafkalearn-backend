from enum import Enum
from typing import Optional, List, Dict, Any
import json
import time
import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    GEMINI = "gemini"
    MISTRAL = "mistral"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"

class LLMClient:
    """
    Client LLM unifié avec fallback automatique et gestion des quotas.
    Logging de chaque appel pour tracer le provider utilisé.
    """

    def __init__(
        self,
        api_keys: Optional[Dict[str, Any]] = None,
        default_provider: LLMProvider = LLMProvider.OPENROUTER,
    ):
        from app.core.config import (
            OPENROUTER_API_KEYS,
            OPENROUTER_MODEL,
            OPENROUTER_MODEL_FALLBACK,
            OLLAMA_URL,
            OLLAMA_MODEL,
        )

        self.api_keys = api_keys or {}
        self.default_provider = default_provider
        self.client = httpx.AsyncClient(timeout=120.0)

        configured_keys = [k for k in OPENROUTER_API_KEYS if k]
        provided_keys = [k for k in self.api_keys.get("openrouter_api_keys", []) if k]
        legacy_single = self.api_keys.get("openrouter", "")
        if legacy_single:
            provided_keys.insert(0, legacy_single)

        merged_keys = provided_keys + configured_keys
        # Préserve l'ordre tout en supprimant les doublons
        self.openrouter_api_keys = list(dict.fromkeys(merged_keys))
        self.openrouter_model = self.api_keys.get("openrouter_model", OPENROUTER_MODEL)
        self.openrouter_model_fallback = self.api_keys.get("openrouter_model_fallback", OPENROUTER_MODEL_FALLBACK)
        self.ollama_url = self.api_keys.get("ollama_url", OLLAMA_URL).rstrip("/")
        self.ollama_model = self.api_keys.get("ollama_model", OLLAMA_MODEL)

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
        messages: Optional[List[Dict[str, str]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
        response_format: Optional[str] = None,  # 'json' pour forcer JSON
        provider: Optional[LLMProvider] = None,
        # Compat legacy
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Génère une réponse via le provider spécifié (ou default).
        Stratégie de fallback :
          - 429 (rate limit) → fallback vers Ollama
          - Réponse JSON invalide → retry OpenRouter
          - Autres erreurs → fallback vers Ollama
        """
        provider = provider or self.default_provider
        max_openrouter_retries = 3

        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        if not messages:
            effective_prompt = user_prompt or prompt
            if effective_prompt:
                messages = [{"role": "user", "content": effective_prompt}]
            else:
                return {"error_code": "LLM_ERROR", "provider": provider.value}

        if not system_instruction and system_prompt:
            system_instruction = system_prompt

        start_ms = time.time() * 1000

        # Log provider selection
        logger.info("LLM call requested: provider=%s, model=%s", provider.value,
                    self.ollama_model if provider == LLMProvider.OLLAMA else self.openrouter_model)

        # ─── Ollama direct ──────────────────────────────────────
        if provider == LLMProvider.OLLAMA:
            logger.info("LLM provider called: Ollama (%s)", self.ollama_model)
            try:
                result = await self._call_ollama(messages, temperature, max_tokens, response_format)
                used_provider = LLMProvider.OLLAMA.value
                latency_ms = int(time.time() * 1000 - start_ms)
                return {
                    **result,
                    "provider": used_provider,
                    "latency_ms": latency_ms,
                    "error_code": None
                }
            except Exception as e:
                logger.error("Ollama generation error: %s", e)
                return {"error_code": "LLM_ERROR", "provider": "ollama"}

        # ─── OpenRouter with retry for invalid JSON, fallback to Ollama for 429 ──
        openrouter_retries = 0
        last_error = None

        while openrouter_retries < max_openrouter_retries:
            try:
                logger.info("LLM provider called: OpenRouter (%s) [attempt %d/%d]",
                            self.openrouter_model, openrouter_retries + 1, max_openrouter_retries)
                result = await self._call_openrouter(messages, temperature, max_tokens, response_format)

                # If we need JSON, validate it
                if response_format == "json":
                    text = result.get("text", "")
                    clean = text.replace("```json", "").replace("```", "").strip()
                    try:
                        json.loads(clean)
                    except (json.JSONDecodeError, ValueError):
                        openrouter_retries += 1
                        logger.warning("Invalid JSON from OpenRouter (attempt %d), retrying...", openrouter_retries)
                        last_error = "INVALID_JSON"
                        continue  # retry OpenRouter

                # Valid JSON or no JSON check needed
                latency_ms = int(time.time() * 1000 - start_ms)
                return {
                    **result,
                    "provider": LLMProvider.OPENROUTER.value,
                    "latency_ms": latency_ms,
                    "error_code": None
                }

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited → fallback to Ollama
                    logger.warning("OpenRouter rate limited (429), fallback to Ollama")
                    break  # exit retry loop, go to Ollama fallback
                elif e.response.status_code in {401, 402, 403}:
                    # Auth error → fallback to Ollama
                    logger.warning("OpenRouter auth error (%d), fallback to Ollama", e.response.status_code)
                    break
                else:
                    logger.error("OpenRouter HTTP %d: %s", e.response.status_code, e.response.text)
                    last_error = f"HTTP_{e.response.status_code}"
                    openrouter_retries += 1

            except Exception as e:
                logger.warning("OpenRouter error: %s", e)
                last_error = str(e)
                openrouter_retries += 1

        # ─── Fallback to Ollama ─────────────────────────────────
        logger.info("LLM provider called: Ollama (%s) [fallback from OpenRouter]", self.ollama_model)
        try:
            result = await self._call_ollama(messages, temperature, max_tokens, response_format)
            latency_ms = int(time.time() * 1000 - start_ms)
            return {
                **result,
                "provider": LLMProvider.OLLAMA.value,
                "latency_ms": latency_ms,
                "error_code": None
            }
        except Exception as e:
            logger.error("Ollama fallback error: %s", e)
            return {"error_code": "LLM_ERROR", "provider": "ollama"}
    
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

    async def _call_mistral(self, messages, temperature, max_tokens, response_format):
        """Appel API Mistral."""
        payload = {
            "model": "mistral-small-latest",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        url = self.endpoints[LLMProvider.MISTRAL]
        response = await self.client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_keys.get('mistral', '')}"},
        )
        response.raise_for_status()
        data = response.json()

        text = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)

        return {"text": text, "tokens_used": tokens}

    async def _call_openrouter(self, messages, temperature, max_tokens, response_format):
        """Appel API OpenRouter."""
        if not self.openrouter_api_keys:
            raise ValueError("OPENROUTER_API_KEY_1..4 non configurees")

        payload = {
            "model": self.openrouter_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        url = self.endpoints[LLMProvider.OPENROUTER]
        last_error = None
        models_to_try = [self.openrouter_model]
        if self.openrouter_model_fallback and self.openrouter_model_fallback != self.openrouter_model:
            models_to_try.append(self.openrouter_model_fallback)

        for model in models_to_try:
            payload["model"] = model
            for index, key in enumerate(self.openrouter_api_keys, start=1):
                response = await self.client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "HTTP-Referer": "https://kafkalearn.app",
                        "X-Title": "KafkaLearn",
                    },
                )

                if response.status_code < 400:
                    data = response.json()
                    msg = data["choices"][0]["message"]
                    text = msg.get("content") or msg.get("reasoning") or ""
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    return {"text": text, "tokens_used": tokens}

                # Rotation clé sur erreurs d'auth/quota
                if response.status_code in {401, 402, 403, 429} and index < len(self.openrouter_api_keys):
                    logger.warning("OpenRouter key #%s en echec (%s), bascule vers la suivante", index, response.status_code)
                    continue

                # Essayer modèle fallback si modèle principal indisponible
                if response.status_code in {400, 404} and model != models_to_try[-1]:
                    logger.warning("Modele OpenRouter '%s' indisponible (%s), tentative fallback", model, response.status_code)
                    last_error = httpx.HTTPStatusError(
                        f"Status {response.status_code}", request=response.request, response=response
                    )
                    break

                last_error = httpx.HTTPStatusError(
                    f"Status {response.status_code}", request=response.request, response=response
                )

            if last_error and getattr(last_error, "response", None) and last_error.response.status_code in {400, 404}:
                continue

        if last_error:
            raise last_error
        raise RuntimeError("Echec OpenRouter: aucune reponse exploitable")

    async def _call_ollama(self, messages, temperature, max_tokens, response_format):
        """Fallback local via Ollama quand OpenRouter échoue."""
        # Use the correct available model
        model = "qwen2.5:7b"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if response_format == "json":
            payload["format"] = "json"

        response = await self.client.post(f"{self.ollama_url}/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        text = data.get("message", {}).get("content", "")
        if not text:
            raise RuntimeError("Ollama a répondu sans contenu exploitable")

        tokens = data.get("eval_count", 0) or 0
        return {"text": text, "tokens_used": tokens}

    async def close(self):
        await self.client.aclose()
