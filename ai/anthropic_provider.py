"""
[DOMAIN: GENERIC]
Anthropic Claude provider.
Use when AI_PROVIDER=anthropic in .env.
Best output quality, requires API key, data leaves local environment.
"""

import logging

import anthropic

from ai.base_provider import AIResponse, BaseAIProvider
from config.settings import AIConfig

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude via API."""

    def __init__(self, config: AIConfig):
        self._config = config
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def complete(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        logger.debug(f"[Anthropic] Sending prompt ({len(prompt)} chars)")

        kwargs = {
            "model": self._config.anthropic_model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        content = response.content[0].text

        logger.debug(f"[Anthropic] Response received ({len(content)} chars)")

        return AIResponse(
            content=content,
            provider=self.provider_name,
            model=self._config.anthropic_model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

    def is_available(self) -> bool:
        try:
            # Minimal call to verify connectivity + API key
            self._client.messages.create(
                model=self._config.anthropic_model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception as e:
            logger.warning(f"[Anthropic] Availability check failed: {e}")
            return False

    @property
    def provider_name(self) -> str:
        return "anthropic"
