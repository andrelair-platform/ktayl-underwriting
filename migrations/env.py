"""Alembic environment. Reads the DB URL from DATABASE_URL (via app config), targets Base.metadata."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import models so their tables are attached to Base.metadata for autogenerate/target compare.
from app.appetite import models as _appetite_models  # noqa: F401,E402
from app.audit import models as _audit_models  # noqa: F401,E402
from app.config import get_settings
from app.db.base import Base
from app.decision import models as _decision_models  # noqa: F401,E402
from app.entity import models as _entity_models  # noqa: F401,E402
from app.submission import models as _submission_models  # noqa: F401,E402

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    # disable_existing_loggers=False is CRITICAL: this app self-migrates on startup (runs alembic
    # in-process in the FastAPI lifespan), and fileConfig defaults to disabling every logger already
    # configured — which silently killed uvicorn's access logs AND the app's request logger after the
    # startup migration ran (the app appeared to log nothing). Keep alembic's config, keep everyone else's.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
