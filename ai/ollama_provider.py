"""
[DOMAIN: GENERIC]
Ollama local LLM provider.
Use when AI_PROVIDER=ollama in .env.
Data never leaves local environment — ideal for NDA / air-gapped projects.
Requires Ollama running locally: https://ollama.ai
"""

import logging

import httpx

from ai.base_provider import AIResponse, BaseAIProvider
from config.settings import AIConfig

logger = logging.getLogger(__name__)


class OllamaProvider(BaseAIProvider):
    """Local LLM via Ollama API."""

    def __init__(self, config: AIConfig):
        self._config = config
        self._base_url = config.ollama_base_url.rstrip("/")

    def complete(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        logger.debug(f"[Ollama] Sending prompt ({len(prompt)} chars) to {self._config.ollama_model}")

        payload = {
            "model": self._config.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=120.0,  # Local models can be slow
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("response", "")

        logger.debug(f"[Ollama] Response received ({len(content)} chars)")

        return AIResponse(
            content=content,
            provider=self.provider_name,
            model=self._config.ollama_model,
            tokens_used=data.get("eval_count"),
        )

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            if self._config.ollama_model not in models:
                logger.warning(
                    f"[Ollama] Model '{self._config.ollama_model}' not found. "
                    f"Available: {models}. Run: ollama pull {self._config.ollama_model}"
                )
                return False
            return True
        except Exception as e:
            logger.warning(f"[Ollama] Availability check failed: {e}. Is Ollama running?")
            return False

    @property
    def provider_name(self) -> str:
        return "ollama"
