"""FastAPI application factory for the underwriting workbench core (UW-01-S01)."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app.api.auth import current_actor
from app.api.routes import ops, v1

# Import the models so their tables are registered on Base.metadata (import side effect).
from app.appetite import models as _appetite_models  # noqa: F401
from app.appetite.repository import seed_v1
from app.audit import models as _audit_models  # noqa: F401
from app.bind import models as _bind_models  # noqa: F401
from app.config import get_settings
from app.db.base import SessionLocal
from app.db.startup import bootstrap_database
from app.decision import models as _decision_models  # noqa: F401
from app.entity import models as _entity_models  # noqa: F401
from app.rating import models as _rating_models  # noqa: F401
from app.rating.repository import seed_v1 as seed_rate_table_v1
from app.submission import models as _submission_models  # noqa: F401

# Log to stdout at INFO so request lines actually show up in `kubectl logs`.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.request")


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

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """One structured INFO line per request: method, path, status, duration, actor (no bodies)."""
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        # Resolve the actor best-effort — never let logging fail a request (e.g. no/invalid token).
        try:
            actor = current_actor(request)
        except Exception:
            actor = "-"
        logger.info(
            "request method=%s path=%s status_code=%s duration_ms=%s actor=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            actor,
        )
        return response

    app.include_router(v1)
    app.include_router(ops)
    return app


app = create_app()
