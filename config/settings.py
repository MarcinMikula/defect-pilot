"""
[DOMAIN: GENERIC]
Configuration loader for defect-pilot.
Reads from .env file and environment variables.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class JiraConfig:
    base_url: str
    email: str
    api_token: str
    project_key: str


@dataclass
class AIConfig:
    provider: str  # "anthropic" | "ollama"
    anthropic_api_key: str | None
    anthropic_model: str
    ollama_base_url: str
    ollama_model: str


@dataclass
class AppConfig:
    jira: JiraConfig
    ai: AIConfig
    db_path: Path
    log_level: str


def load_config() -> AppConfig:
    """Load and validate configuration from environment."""

    ai_provider = os.getenv("AI_PROVIDER", "ollama").lower()
    if ai_provider not in ("anthropic", "ollama"):
        raise ValueError(f"AI_PROVIDER must be 'anthropic' or 'ollama', got: '{ai_provider}'")

    jira_config = JiraConfig(
        base_url=_require("JIRA_BASE_URL"),
        email=_require("JIRA_EMAIL"),
        api_token=_require("JIRA_API_TOKEN"),
        project_key=os.getenv("JIRA_PROJECT_KEY", "PROJ"),
    )

    ai_config = AIConfig(
        provider=ai_provider,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3"),
    )

    if ai_provider == "anthropic" and not ai_config.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic")

    return AppConfig(
        jira=jira_config,
        ai=ai_config,
        db_path=Path(os.getenv("DB_PATH", "./data/defects.db")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def _require(key: str) -> str:
    """Get env variable or raise with a helpful message."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Required environment variable '{key}' is not set. Check your .env file.")
    return value
