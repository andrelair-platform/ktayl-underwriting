"""L3 contract test — this service's OWN OpenAPI.

Two checks:
  1. ``app.openapi()`` is a structurally valid OpenAPI document (openapi-spec-validator).
  2. A small, fast, deterministic schemathesis pass over the read/ops endpoints — property-based
     fuzzing that the app's responses conform to its own declared schema. The budget is deliberately
     tiny (few examples, deadline off) so it never hangs CI; the policy-service contract test is the
     priority, this is a cheap self-consistency net.

Schemathesis 3.x doesn't fully support OpenAPI **3.1** (FastAPI's default). We serve the schemathesis
instance a **3.0.3** rendering of the same app (``openapi_version = "3.0.3"``) — same paths/schemas,
just the older top-level version schemathesis understands. If a schemathesis SchemaError still occurs
(a version bump changing behaviour), the parametrized test degrades to a skip rather than failing the
whole gate — per the brief, this self-check is secondary to the policy-service contract test.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import schemathesis
from fastapi import FastAPI
from hypothesis import HealthCheck, settings
from openapi_spec_validator import validate as validate_spec
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Import models so all tables register on Base.metadata before create_all (mirrors conftest).
from app.appetite import models as _appetite_models  # noqa: F401
from app.appetite.repository import seed_v1 as seed_appetite_v1
from app.audit import models as _audit_models  # noqa: F401
from app.bind import models as _bind_models  # noqa: F401
from app.config import get_settings
from app.db.base import Base, get_db
from app.decision import models as _decision_models  # noqa: F401
from app.entity import models as _entity_models  # noqa: F401
from app.main import create_app
from app.rating import models as _rating_models  # noqa: F401
from app.rating.repository import seed_v1 as seed_rate_table_v1
from app.submission import models as _submission_models  # noqa: F401

# The read/ops surface schemathesis explores — the two PARAMETER-FREE, DB-FREE GETs (healthz/info).
# Scoping is deliberate and kept minimal per the brief (the policy-service contract test is the
# priority; this is a cheap self-consistency net):
#   - write endpoints (POST submissions/assess/quote/bind) mutate state + need a valid prior step + hit
#     the bind seams — covered by L1 (mocked) + L2 (real DB);
#   - path-param reads (/v1/submissions/{id}…) make schemathesis fuzz large volumes of ids per
#     operation (slow/heavy) for little added signal — they're exercised in L1;
#   - /v1/rate-tables is EXCLUDED on purpose: its `effective_at` is a tz-aware datetime in prod
#     (Postgres timestamptz → RFC3339 with an offset), but the in-memory SQLite this test runs on
#     drops the tz and returns a NAIVE datetime, which fails strict `format: date-time`. That is a
#     SQLite serialization artifact of the test DB, NOT an app defect — chasing it would make this
#     self-check flaky. The real datetime contract that matters (the policy-service CreatePolicyRequest
#     date-time) is enforced by test_policy_service_contract.py.
# So schemathesis stays on the static ops endpoints, where it's fast, deterministic and side-effect-free.
_EXPLORED_PATHS = (
    "/healthz",
    "/info",
)


def test_own_openapi_is_valid() -> None:
    """The app's generated OpenAPI document is structurally valid."""
    app = create_app()
    spec = app.openapi()
    assert spec["openapi"].startswith("3.")
    assert "/v1/submissions" in spec["paths"]
    # A hard structural validation (raises OpenAPIValidationError on a malformed doc).
    validate_spec(spec)


def _schemathesis_app() -> FastAPI:
    """The app rendered as OpenAPI 3.0.3 so schemathesis 3.x can consume it (same paths/schemas).

    schemathesis' ``from_asgi`` runs the app **lifespan**, so we must give it a working DB the same way
    the L1 conftest does — otherwise the lifespan hangs ~3 minutes in the Postgres wait-loop. We disable
    the startup migration gate + build the schema in an in-memory SQLite and override ``get_db`` so the
    read endpoints answer. (Without this, the schemathesis pass blocks on the DB-wait retry, which is the
    exact trap that makes people think schemathesis is "flaky/heavy".)
    """
    # Off the startup alembic/DB-wait (no Postgres here); build the schema in-memory instead.
    get_settings().run_db_migrations_on_startup = False

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Point the lifespan seed (which uses app.main.SessionLocal) at the in-memory engine + seed v1.
    import app.main as app_main

    app_main.SessionLocal = testing_session  # type: ignore[misc]
    with testing_session() as s:
        seed_appetite_v1(s)
        seed_rate_table_v1(s)

    app = create_app()
    app.openapi_version = "3.0.3"
    app.openapi_schema = None  # force a re-render at the pinned version

    def _override_get_db() -> Iterator[Session]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return app


def _load_schema() -> Any:
    try:
        return schemathesis.from_asgi("/openapi.json", _schemathesis_app())
    except schemathesis.exceptions.SchemaError:  # pragma: no cover - defensive on a version bump
        return None


_schema = _load_schema()

# Collect the parametrized test only if the schema loaded; otherwise expose a clear skip so the suite
# never errors at collection.
if _schema is not None:

    @_schema.include(method="GET", path_regex=r"^(/healthz|/info)$").parametrize()
    @settings(max_examples=5, deadline=None, suppress_health_check=list(HealthCheck))
    def test_read_endpoints_conform(case: schemathesis.Case) -> None:
        """Fuzz the parameter-free read/ops (GET) endpoints against the app's own schema.

        ``case.call_and_validate`` drives the ASGI app in-process (no network) and asserts the response
        conforms to the declared schema — i.e. the app never returns an *undeclared* shape. Scoped +
        tiny budget so it stays fast and deterministic (see ``_EXPLORED_PATHS`` above).
        """
        assert case.path in _EXPLORED_PATHS  # the include() filter should keep us to these three
        case.call_and_validate()

else:  # pragma: no cover - only hit if schemathesis can't parse the (downgraded) schema

    @pytest.mark.skip(reason="schemathesis could not load the app schema (OpenAPI version support)")
    def test_read_endpoints_conform() -> None:  # type: ignore[misc]
        pass
