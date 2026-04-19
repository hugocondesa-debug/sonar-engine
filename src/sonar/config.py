"""Runtime configuration via pydantic-settings.

Loads from `.env` at repo root (gitignored). Secrets never checked in —
`.env.example` is the template.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """SONAR runtime settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    fred_api_key: str = Field(
        ...,
        description="Federal Reserve Economic Data API key (https://fred.stlouisfed.org/docs/api/api_key.html).",
    )
    database_url: str = Field(
        default="sqlite:///./data/sonar-dev.db",
        description="SQLAlchemy DSN — Phase 1 MVP usa SQLite local gitignored.",
    )
    cache_dir: Path = Field(
        default=Path("./data/cache"),
        description="Diskcache directory para L0 connectors.",
    )


settings = Settings()
