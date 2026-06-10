"""
[DOMAIN: GENERIC]
Abstract base class for AI providers.
All providers must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
    content: str
    provider: str
    model: str
    tokens_used: int | None = None


class BaseAIProvider(ABC):
    """
    Abstract AI provider interface.

    Implementations:
    - AnthropicProvider  (claude via API)
    - OllamaProvider     (local LLM)
    """

    @abstractmethod
    def complete(self, prompt: str, system_prompt: str | None = None) -> AIResponse:
        """
        Send a prompt and return a response.

        Args:
            prompt: User prompt
            system_prompt: Optional system/context prompt

        Returns:
            AIResponse with content and metadata
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is reachable / configured correctly.
        Used at startup to fail fast with a helpful error.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging."""
        ...
