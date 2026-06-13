"""
[DOMAIN: GENERIC]
Ollama local LLM provider.
Use when AI_PROVIDER=ollama in .env.
Data never leaves local environment — ideal for NDA / air-gapped projects.
Requires Ollama running locally: https://ollama.ai

Vision support: depends on model
  - llava, llava-phi3, bakllava  → supports images ✅
  - llama3.2, mistral, gemma     → text only ❌
"""

import base64
import logging

import httpx

from ai.base_provider import AIResponse, BaseAIProvider
from config.settings import AIConfig

logger = logging.getLogger(__name__)

# Models known to support vision — used for is_available() hint only
# Not exhaustive — Ollama adds new vision models regularly
_VISION_MODELS = {"llava", "llava-phi3", "llava-llama3", "bakllava", "moondream"}


class OllamaProvider(BaseAIProvider):
    """Local LLM via Ollama API. Supports vision when using llava-family models."""

    def __init__(self, config: AIConfig):
        self._config = config
        self._base_url = config.ollama_base_url.rstrip("/")
        self._model = config.ollama_model
        self._supports_vision = any(
            v in self._model.lower() for v in _VISION_MODELS
        )
        if self._supports_vision:
            logger.info(f"[Ollama] Model '{self._model}' — vision supported ✅")
        else:
            logger.info(f"[Ollama] Model '{self._model}' — text only (no vision)")

    def complete(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        logger.debug(f"[Ollama] Sending prompt ({len(prompt)} chars) to {self._model}")

        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=300.0,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("response", "")

        logger.debug(f"[Ollama] Response received ({len(content)} chars)")

        return AIResponse(
            content=content,
            provider=self.provider_name,
            model=self._model,
            tokens_used=data.get("eval_count"),
        )

    def complete_with_images(
        self,
        prompt: str,
        images_b64: list[str],
        system_prompt: str | None = None,
        media_type: str = "image/png",
    ) -> AIResponse:
        """
        Send prompt + images to Ollama vision model (llava family).
        Ollama /api/generate accepts base64 images in the 'images' field.

        Args:
            prompt: Text prompt
            images_b64: List of base64-encoded images
            system_prompt: Optional system prompt
            media_type: Ignored for Ollama (base64 only, no MIME needed)
        """
        if not self._supports_vision:
            logger.warning(
                f"[Ollama] Model '{self._model}' may not support vision. "
                f"Consider switching to llava. Attempting anyway..."
            )

        logger.debug(
            f"[Ollama] Sending multimodal prompt "
            f"({len(prompt)} chars + {len(images_b64)} image(s)) to {self._model}"
        )

        payload = {
            "model": self._model,
            "prompt": prompt,
            "images": images_b64,   # Ollama accepts raw base64, no data URI prefix
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        response = httpx.post(
            f"{self._base_url}/api/generate",
            json=payload,
            timeout=300.0,   # Vision models are slower
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("response", "")

        logger.debug(f"[Ollama] Vision response received ({len(content)} chars)")

        return AIResponse(
            content=content,
            provider=self.provider_name,
            model=self._model,
            tokens_used=data.get("eval_count"),
        )

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            model_names = [m.split(":")[0] for m in models]
            if self._model.split(":")[0] not in model_names:
                logger.warning(
                    f"[Ollama] Model '{self._model}' not found. "
                    f"Available: {models}. Run: ollama pull {self._model}"
                )
                return False
            return True
        except Exception as e:
            logger.warning(f"[Ollama] Availability check failed: {e}. Is Ollama running?")
            return False

    @property
    def provider_name(self) -> str:
        return "ollama"
