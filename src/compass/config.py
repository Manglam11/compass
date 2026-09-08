"""Compass runtime configuration.

Non-secret defaults live in config/default.yaml. Secrets are read from
environment variables only (see .env.example for the expected names) and
are never written to any file in this repo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "default.yaml"


def load_default_yaml(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COMPASS_", env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
