import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _environment_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    environment: str
    database_path: Path
    session_secret: str
    ai_provider: str
    cookie_secure: bool
    project_status_enabled: bool
    login_max_attempts: int
    login_lockout_minutes: int
    login_window_minutes: int
    session_idle_minutes: int
    session_absolute_hours: int
    max_sessions_per_account: int
    temp_password_hours: int
    app_version: str
    dev_server_enabled: bool
    debug_enabled: bool


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development")
    database_value = os.getenv("DATABASE_PATH", str(PROJECT_ROOT / "data" / "dev" / "app.db"))
    session_secret = os.getenv("SESSION_SECRET", "development-only-change-me")
    dev_server_enabled = _environment_flag("DEV_SERVER_ENABLED", environment == "development")
    debug_enabled = _environment_flag("DEBUG", environment == "development")

    if environment in ("production", "trial") and session_secret == "development-only-change-me":
        raise RuntimeError("SESSION_SECRET_REQUIRED_IN_PRODUCTION_OR_TRIAL")

    return Settings(
        environment=environment,
        database_path=Path(database_value),
        session_secret=session_secret,
        ai_provider=os.getenv("AI_PROVIDER", "mock"),
        cookie_secure=environment in ("production", "trial"),
        project_status_enabled=_environment_flag(
            "PROJECT_STATUS_ENABLED", environment != "production"
        ),
        login_max_attempts=_env_int("LOGIN_MAX_ATTEMPTS", 5),
        login_lockout_minutes=_env_int("LOGIN_LOCKOUT_MINUTES", 15),
        login_window_minutes=_env_int("LOGIN_WINDOW_MINUTES", 15),
        session_idle_minutes=_env_int("SESSION_IDLE_MINUTES", 30),
        session_absolute_hours=_env_int("SESSION_ABSOLUTE_HOURS", 12),
        max_sessions_per_account=_env_int("MAX_SESSIONS_PER_ACCOUNT", 2),
        temp_password_hours=_env_int("TEMP_PASSWORD_HOURS", 24),
        app_version="0.1.0",
        dev_server_enabled=dev_server_enabled,
        debug_enabled=debug_enabled,
    )


_VALID_ENVIRONMENTS = frozenset({"development", "trial", "production"})


def validate_deployment_safety(settings: Settings) -> list[str]:
    """Return a list of safety violations. Empty list means safe to start."""
    violations: list[str] = []

    if settings.environment not in _VALID_ENVIRONMENTS:
        violations.append(
            f"UNKNOWN_ENVIRONMENT:{settings.environment}"
        )

    if settings.environment in ("production", "trial"):
        if not settings.cookie_secure:
            violations.append("COOKIE_SECURE_MUST_BE_ENABLED_IN_PRODUCTION_OR_TRIAL")
        if settings.dev_server_enabled:
            violations.append("DEV_SERVER_MUST_BE_DISABLED_IN_PRODUCTION_OR_TRIAL")
        if settings.debug_enabled:
            violations.append("DEBUG_MUST_BE_DISABLED_IN_PRODUCTION_OR_TRIAL")

        https_url = os.getenv("HTTPS_BASE_URL", "")
        if not https_url or not https_url.startswith("https://"):
            violations.append(
                "HTTPS_BASE_URL_MUST_BE_CONFIGURED_IN_PRODUCTION_OR_TRIAL"
            )

    return violations
