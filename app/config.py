"""Runtime configuration (env-driven, per the env-agnostic-image convention)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_VERSION_FILE = Path(__file__).resolve().parent.parent / "version.txt"


def _read_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


class Settings(BaseSettings):
    """Service settings. All values are read at runtime from the environment."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    service_name: str = "ktayl-underwriting"
    # Generic dev default; overridden by DATABASE_URL in every real environment.
    database_url: str = "postgresql+psycopg://underwriting:underwriting@localhost:5432/underwriting"

    @property
    def version(self) -> str:
        return _read_version()


@lru_cache
def get_settings() -> Settings:
    return Settings()
