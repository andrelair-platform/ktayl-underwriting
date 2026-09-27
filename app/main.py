"""FastAPI application factory for the underwriting workbench core (UW-01-S01)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import ops, v1

# Import the models so their tables are registered on Base.metadata (import side effect).
from app.appetite import models as _appetite_models  # noqa: F401
from app.appetite.repository import seed_v1
from app.audit import models as _audit_models  # noqa: F401
from app.config import get_settings
from app.db.base import SessionLocal
from app.db.startup import bootstrap_database
from app.decision import models as _decision_models  # noqa: F401
from app.entity import models as _entity_models  # noqa: F401
from app.rating import models as _rating_models  # noqa: F401
from app.rating.repository import seed_v1 as seed_rate_table_v1
from app.submission import models as _submission_models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Self-migrate on startup: wait for the DB, then `alembic upgrade head` (a separate migration
    # Job would deadlock the ArgoCD sync ordering — the platform standard is to self-migrate). Gated
    # off in L1 tests, which build the schema in-memory instead of via Alembic.
    if get_settings().run_db_migrations_on_startup:
        bootstrap_database()
    # Seed appetite ruleset v1 + rate table v1 if none exist (idempotent), against the migrated schema.
    with SessionLocal() as session:
        seed_v1(session)
        seed_rate_table_v1(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ktayl-underwriting",
        version=settings.version,
        summary="Underwriting workbench core — intake, appetite/eligibility, decision, audit (UW-01-S01)",
        lifespan=lifespan,
    )
    app.include_router(v1)
    app.include_router(ops)
    return app


app = create_app()
