"""
Unit tests for config/settings.py
"""

import os
import pytest
from unittest.mock import patch

from config.settings import load_config, _require


class TestRequire:
    def test_returns_value_when_set(self):
        with patch.dict(os.environ, {"MY_VAR": "hello"}):
            assert _require("MY_VAR") == "hello"

    def test_raises_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MY_VAR", None)
            with pytest.raises(ValueError, match="MY_VAR"):
                _require("MY_VAR")


class TestLoadConfig:
    BASE_ENV = {
        "AI_PROVIDER": "ollama",
        "JIRA_BASE_URL": "https://test.atlassian.net",
        "JIRA_EMAIL": "test@test.com",
        "JIRA_API_TOKEN": "token123",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "llama3",
    }

    def test_loads_ollama_config(self):
        with patch.dict(os.environ, self.BASE_ENV, clear=True):
            config = load_config()
            assert config.ai.provider == "ollama"
            assert config.jira.base_url == "https://test.atlassian.net"

    def test_raises_on_invalid_provider(self):
        env = {**self.BASE_ENV, "AI_PROVIDER": "gpt-banana"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="AI_PROVIDER"):
                load_config()

    def test_raises_on_anthropic_without_key(self):
        env = {**self.BASE_ENV, "AI_PROVIDER": "anthropic"}
        env.pop("ANTHROPIC_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                load_config()
