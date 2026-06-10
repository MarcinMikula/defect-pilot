"""
[DOMAIN: GENERIC]
Factory for AI providers.
Instantiates the correct provider based on config.
"""

from ai.anthropic_provider import AnthropicProvider
from ai.base_provider import BaseAIProvider
from ai.ollama_provider import OllamaProvider
from config.settings import AIConfig


def get_provider(config: AIConfig) -> BaseAIProvider:
    """
    Return the configured AI provider instance.

    Args:
        config: AIConfig with provider selection and credentials

    Returns:
        Configured BaseAIProvider implementation

    Raises:
        ValueError: If provider is unknown
    """
    match config.provider:
        case "anthropic":
            return AnthropicProvider(config)
        case "ollama":
            return OllamaProvider(config)
        case _:
            raise ValueError(
                f"Unknown AI provider: '{config.provider}'. "
                "Valid options: 'anthropic', 'ollama'"
            )
