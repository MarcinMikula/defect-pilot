"""
[DOMAIN: GENERIC]
Anthropic Claude provider.
Use when AI_PROVIDER=anthropic in .env.
Supports multimodal (text + images) via Claude's vision capability.
"""

import logging

import anthropic

from ai.base_provider import AIResponse, BaseAIProvider
from config.settings import AIConfig

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude via API. Supports vision (multimodal)."""

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

        return AIResponse(
            content=content,
            provider=self.provider_name,
            model=self._config.anthropic_model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

    def complete_with_images(
        self,
        prompt: str,
        images_b64: list[str],
        system_prompt: str | None = None,
        media_type: str = "image/png",
    ) -> AIResponse:
        """
        Send prompt + images to Claude vision.

        Args:
            prompt: Text prompt
            images_b64: List of base64-encoded images
            system_prompt: Optional system prompt
            media_type: MIME type for all images (default: image/png)
        """
        logger.debug(
            f"[Anthropic] Sending multimodal prompt "
            f"({len(prompt)} chars + {len(images_b64)} image(s))"
        )

        # Build content blocks: images first, then text
        content = []
        for img_b64 in images_b64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": img_b64,
                },
            })
        content.append({"type": "text", "text": prompt})

        kwargs = {
            "model": self._config.anthropic_model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": content}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self._client.messages.create(**kwargs)
        text_content = response.content[0].text

        return AIResponse(
            content=text_content,
            provider=self.provider_name,
            model=self._config.anthropic_model,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

    def is_available(self) -> bool:
        try:
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
