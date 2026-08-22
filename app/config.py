"""Compatibility import for code being migrated to the core package."""

from app.core.config import PROJECT_ROOT, Settings, get_settings

__all__ = ["PROJECT_ROOT", "Settings", "get_settings"]
