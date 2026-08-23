"""Minimal configuration for the standalone, local-only delivery dashboard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _environment_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    project_status_enabled: bool


def get_settings() -> Settings:
    return Settings(project_status_enabled=_environment_flag("PROJECT_STATUS_ENABLED", True))
