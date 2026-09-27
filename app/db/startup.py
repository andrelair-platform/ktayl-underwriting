"""Startup DB bootstrap: wait for Postgres, then run Alembic migrations in-process.

The platform standard (see ktayl-policy-service) is to **self-migrate on startup** rather than run
a separate migration Job: a separate Job creates an ArgoCD ordering deadlock (it depends on the CNPG
DB, created in the same sync). So the app waits for its DB, runs ``alembic upgrade head``, and only
then serves. Both steps are idempotent and safe to run on every pod start.

Neither step runs under L1 tests: they are gated by ``settings.run_db_migrations_on_startup`` (the
test conftest sets it False) and the test schema is created via ``Base.metadata.create_all`` against
an in-memory SQLite engine, never via Alembic.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Repo root (…/app/db/startup.py -> …/) holds alembic.ini + migrations/.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"

# Bounded retry so a first install (CNPG still bootstrapping) crash-loops gracefully rather than
# erroring hard: ~60 attempts × 3s ≈ 3 minutes before giving up.
_WAIT_MAX_ATTEMPTS = 60
_WAIT_INTERVAL_SECONDS = 3.0


def wait_for_db(
    database_url: str,
    *,
    max_attempts: int = _WAIT_MAX_ATTEMPTS,
    interval_seconds: float = _WAIT_INTERVAL_SECONDS,
) -> None:
    """Block until the DB accepts a connection, or raise after ``max_attempts`` tries.

    Each attempt runs a trivial ``SELECT 1``. On a fresh install the CNPG cluster may not be ready
    yet, so failures are logged and retried on a fixed interval instead of failing fast.
    """
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        for attempt in range(1, max_attempts + 1):
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                logger.info("Database is accepting connections (attempt %d/%d).", attempt, max_attempts)
                return
            except OperationalError as exc:
                logger.warning(
                    "Database not ready (attempt %d/%d): %s. Retrying in %.1fs.",
                    attempt,
                    max_attempts,
                    exc.__class__.__name__,
                    interval_seconds,
                )
                if attempt < max_attempts:
                    time.sleep(interval_seconds)
        raise RuntimeError(f"Database did not become available after {max_attempts} attempts.")
    finally:
        engine.dispose()


def run_migrations() -> None:
    """Run ``alembic upgrade head`` in-process against the app's DATABASE_URL. Idempotent."""
    settings = get_settings()
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_REPO_ROOT / "migrations"))
    # migrations/env.py reads the URL from app config; set it explicitly too so the Config is
    # self-contained regardless of how env.py resolves it.
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    logger.info("Running alembic upgrade head.")
    command.upgrade(cfg, "head")
    logger.info("Migrations up to date.")


def bootstrap_database() -> None:
    """Wait for the DB, then bring the schema to head. Called from the FastAPI lifespan."""
    settings = get_settings()
    wait_for_db(settings.database_url)
    run_migrations()
