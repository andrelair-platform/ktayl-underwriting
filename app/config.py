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
    # Self-migrate on startup (wait for DB → alembic upgrade head) before serving. Disabled in L1
    # tests, which create the schema in-memory via Base.metadata.create_all instead of Alembic.
    run_db_migrations_on_startup: bool = True

    # --- Bind to the live policy service (ADR-006) --------------------------------------------
    # The live ktayl-policy-service base URL; the UW service binds risk into it (create→submit→activate).
    policy_service_url: str = "http://ktayl-policy-service.default.svc:8080"
    # NATS URL for the bound-risk event (the reinsurance/actuarial seam). Empty = no publish target.
    nats_url: str = ""
    # OAuth2 client-credentials (Authentik) for the PAS token (scope policy:write). Empty in dev.
    oidc_token_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_scope: str = "policy:write"

    @property
    def version(self) -> str:
        return _read_version()


@lru_cache
def get_settings() -> Settings:
    return Settings()
