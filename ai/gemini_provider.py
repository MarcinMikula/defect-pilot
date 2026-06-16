"""
[DOMAIN: GENERIC]
Gemini AI provider — used for Playwright script generation (Option B).

Unlike ollama/anthropic which are used for defect enrichment,
Gemini is used exclusively for code generation. Data sent:
enriched defect fields only (steps, URL, expected/actual, UI elements)
— not raw Jira ticket content.

Free tier: 15 requests/min, 1500/day — sufficient for script generation.
Docs: https://ai.google.dev/gemini-api/docs
"""

import logging

from google import genai
from google.genai import types

from ai.base_provider import BaseAIProvider, AIResponse
from config.settings import AIConfig

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini provider for code generation.

    Used for Option B Playwright script generation.
    Requires GEMINI_API_KEY in .env.
    """

    def __init__(self, config: AIConfig):
        api_key = config.gemini_api_key
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is required for script generation.\n"
                "Get a free key at: https://aistudio.google.com/apikey\n"
                "Add to .env: GEMINI_API_KEY=AIza..."
            )
        self._client = genai.Client(api_key=api_key)
        self._model_name = config.gemini_model or "gemini-2.0-flash"
        logger.info(f"[Gemini] Initialized — model: {self._model_name}")

    @property
    def provider_name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        """Check if Gemini API is reachable and key is valid."""
        try:
            self._client.models.get(model=self._model_name)
            return True
        except Exception as e:
            logger.warning(f"[Gemini] Availability check failed: {e}")
            return False

    def complete(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        """
        Generate text completion via Gemini.

        Args:
            prompt: User prompt
            system_prompt: System instructions

        Returns:
            AIResponse with generated content
        """
        config = None
        if system_prompt:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
            )

        logger.debug(f"[Gemini] Sending request to {self._model_name}")
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=config,
        )

        content = response.text
        logger.debug(f"[Gemini] Response received — {len(content)} chars")

        return AIResponse(
            content=content,
            provider="gemini",
            model=self._model_name,
        )