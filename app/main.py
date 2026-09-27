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
from app.decision import models as _decision_models  # noqa: F401
from app.entity import models as _entity_models  # noqa: F401
from app.submission import models as _submission_models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Seed appetite ruleset v1 if none exists (idempotent). Schema itself is managed by Alembic.
    with SessionLocal() as session:
        seed_v1(session)
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
