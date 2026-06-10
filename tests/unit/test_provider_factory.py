"""
Unit tests for ai/provider_factory.py
"""

import pytest

from ai.anthropic_provider import AnthropicProvider
from ai.ollama_provider import OllamaProvider
from ai.provider_factory import get_provider
from config.settings import AIConfig


def make_config(provider: str) -> AIConfig:
    return AIConfig(
        provider=provider,
        anthropic_api_key="sk-ant-test" if provider == "anthropic" else None,
        anthropic_model="claude-sonnet-4-20250514",
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3",
    )


class TestGetProvider:
    def test_returns_ollama_provider(self):
        provider = get_provider(make_config("ollama"))
        assert isinstance(provider, OllamaProvider)
        assert provider.provider_name == "ollama"

    def test_returns_anthropic_provider(self):
        provider = get_provider(make_config("anthropic"))
        assert isinstance(provider, AnthropicProvider)
        assert provider.provider_name == "anthropic"

    def test_raises_on_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown AI provider"):
            get_provider(make_config("gpt-banana"))
