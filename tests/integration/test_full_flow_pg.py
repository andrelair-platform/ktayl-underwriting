"""L2 integration test — the full underwriting flow against a REAL Postgres.

This is what a SQLite-only L1 suite can't prove: that the schema our Alembic migrations produce, on
the real database engine, actually supports the whole flow — with the real repositories, real
services, and real ``session.commit()`` semantics. Only the two EXTERNAL boundaries are faked (the
policy-service HTTP client + the NATS publisher, reused from ``tests/fixtures/bind.py``); everything
DB-side is real.

Flow: intake → assess (accept) → quote → bind. Then we assert against the REAL DB:
  - the submission / decision / quote / binding rows exist and reconcile,
  - the appetite ruleset v1 + rate table v1 seeds are present,
  - Alembic is at ``head``,
  - a DB-level invariant holds (binding.policy_number is UNIQUE — a second insert of the same number
    is rejected by Postgres).

Skips cleanly when Docker is unavailable (``pytest.importorskip`` + a docker-ping), so ``make test``
(L1, no Docker) stays green locally; CI runs it on the Docker-capable ubuntu-latest runner.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.appetite.models import AppetiteRuleset  # noqa: E402
from app.appetite.repository import SqlAppetiteRepository  # noqa: E402
from app.appetite.repository import seed_v1 as seed_appetite_v1  # noqa: E402
from app.audit.repository import SqlAuditRepository  # noqa: E402
from app.bind import service as bind_service  # noqa: E402
from app.bind.models import Binding  # noqa: E402
from app.bind.repository import SqlBindingRepository  # noqa: E402
from app.decision.models import Decision  # noqa: E402
from app.entity.repository import SqlCounterpartyRepository  # noqa: E402
from app.rating import service as rating_service  # noqa: E402
from app.rating.models import Quote, RateTable  # noqa: E402
from app.rating.repository import SqlQuoteRepository, SqlRateTableRepository  # noqa: E402
from app.rating.repository import seed_v1 as seed_rate_table_v1  # noqa: E402
from app.submission import service as submission_service  # noqa: E402
from app.submission.schemas import SubmissionCreate  # noqa: E402
from tests.fixtures.bind import FakeBoundRiskPublisher, FakePolicyServiceClient  # noqa: E402
from tests.fixtures.submissions import submission_payload  # noqa: E402

_ACTOR = "integration-test"

# L2 needs a REAL Postgres. Prefer a CI-provided one via env TEST_DATABASE_URL (a GitHub Actions service
# container — the deterministic reference pattern; testcontainers' get_connection_url flaked on the runner);
# fall back to a throwaway testcontainers Postgres when Docker is available locally; else skip so a bare L1
# env stays green.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")


def _psycopg_url(url: str) -> str:
    return url if "+psycopg" in url else url.replace("postgresql://", "postgresql+psycopg://", 1)


def _assert_disposable(url: str) -> None:
    """SAFETY: this test DROPs the schema — refuse to run against anything that isn't an obviously
    disposable test database. A GH Actions service container / local docker (localhost + a db name
    containing 'test') is fine; a real dev/prod cluster DB must NEVER be reachable here. Fail loudly
    rather than wipe a real database if TEST_DATABASE_URL is ever mis-pointed."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    dbname = (parsed.path or "").lstrip("/").lower()
    is_local = host in {"localhost", "127.0.0.1", "::1", ""}
    is_test_db = "test" in dbname
    if not (is_local and is_test_db):
        raise RuntimeError(
            f"REFUSING to run the destructive L2 integration test against host={host!r} db={dbname!r}. "
            "It must be a disposable test DB (localhost + a name containing 'test'). "
            "NEVER point TEST_DATABASE_URL at a dev/prod database — this test DROPs the schema."
        )


def _docker_available() -> bool:
    """True only if a Docker daemon is reachable (so we skip rather than error without it)."""
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _TEST_DB_URL and not _docker_available(),
    reason="L2 needs a real Postgres: set TEST_DATABASE_URL (CI service container) or provide Docker",
)


def _migrated_factory(url: str, *, clean_first: bool) -> Iterator[sessionmaker[Session]]:
    """Migrate ``url`` with REAL Alembic (``upgrade head`` — the app's own startup path, not a
    ``create_all`` shortcut), then yield a session factory. ``clean_first`` drops+recreates the public
    schema so a re-used CI database starts clean and the run is idempotent."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.config import get_settings
    from app.db import startup as db_startup

    engine = create_engine(url, pool_pre_ping=True)
    if clean_first:
        # HARD SAFETY: clean_first DROPs the schema. Refuse outright unless `url` is an obviously
        # disposable test DB — this makes the destructive path incapable of hitting a real database,
        # not merely "configured not to".
        _assert_disposable(url)
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"))

    # migrations/env.py resolves its URL from the app's own settings (get_settings().database_url,
    # i.e. DATABASE_URL) and OVERWRITES cfg's sqlalchemy.url — the app self-migrates on startup, so
    # that's correct for the app. Point the app's DATABASE_URL at THIS test DB (and clear the lru_cache)
    # so the in-process alembic run migrates the DB we're actually testing, not the app's default DSN.
    _prev_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()

    cfg = Config(str(db_startup._ALEMBIC_INI))
    cfg.set_main_option("script_location", str(db_startup._REPO_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # The migrations seed appetite v1 + rate table v1; seed_v1 is idempotent (documents startup seeding).
    with factory() as s:
        seed_appetite_v1(s)
        seed_rate_table_v1(s)
    try:
        yield factory
    finally:
        engine.dispose()
        # Restore the process DATABASE_URL so a combined run (unit+integration) isn't left mutated.
        if _prev_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = _prev_database_url
        get_settings.cache_clear()


@pytest.fixture(scope="module")
def pg_session_factory() -> Iterator[sessionmaker[Session]]:
    """A real Postgres — a CI service container (``TEST_DATABASE_URL``) or a throwaway testcontainers one —
    migrated with REAL Alembic (``upgrade head``)."""
    if _TEST_DB_URL:
        yield from _migrated_factory(_psycopg_url(_TEST_DB_URL), clean_first=True)
    else:
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
            yield from _migrated_factory(_psycopg_url(postgres.get_connection_url()), clean_first=False)


@pytest.fixture
def session(pg_session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with pg_session_factory() as s:
        yield s


def _intake_assess_quote_bind(session: Session, **overrides: Any) -> tuple[str, Binding]:
    """Run the full flow through the real services + repos against the real DB."""
    counterparties = SqlCounterpartyRepository(session)
    appetite = SqlAppetiteRepository(session)
    audit = SqlAuditRepository(session)
    rate_tables = SqlRateTableRepository(session)
    quotes = SqlQuoteRepository(session)
    bindings = SqlBindingRepository(session)

    payload = SubmissionCreate.model_validate(submission_payload(**overrides))
    submission = submission_service.create_submission(session, payload, counterparties, audit, actor=_ACTOR)

    decision = submission_service.assess_submission(session, submission.id, appetite, audit, actor=_ACTOR)
    assert decision.outcome == "accept"

    rating_service.quote_submission(session, submission.id, rate_tables, quotes, audit, actor=_ACTOR)

    binding = bind_service.bind_submission(
        session,
        submission.id,
        bindings,
        quotes,
        audit,
        FakePolicyServiceClient(),
        FakeBoundRiskPublisher(),
        actor=_ACTOR,
    )
    return submission.id, binding


def test_full_flow_persists_all_rows(session: Session) -> None:
    """intake → assess → quote → bind persists a reconciling row in every table (real Postgres)."""
    submission_id, binding = _intake_assess_quote_bind(session)

    # Binding row is real, bound, and links back to the submission + quote.
    assert binding.status == "bound"
    assert binding.submission_id == submission_id
    assert binding.policy_number.startswith("UW-")
    assert binding.event_published is True

    # Every upstream row exists and reconciles.
    decision = session.scalar(select(Decision).where(Decision.submission_id == submission_id))
    assert decision is not None and decision.outcome == "accept"
    quote = session.scalar(select(Quote).where(Quote.submission_id == submission_id))
    assert quote is not None and quote.premium_minor == 31_250  # warehouse €500k @ 0.5‰ × 1.25
    assert binding.quote_id == quote.id

    # The full audit trail landed, in order.
    audit_rows = SqlAuditRepository(session).list_for_submission(submission_id)
    assert [a.action for a in audit_rows] == ["submission.created", "submission.assessed", "quote", "bind"]


def test_seeds_present_on_migrated_db(session: Session) -> None:
    """The Alembic migrations + startup seed leave appetite ruleset v1 and rate table v1 in place."""
    ruleset = session.scalar(select(AppetiteRuleset).where(AppetiteRuleset.version == 1))
    assert ruleset is not None
    assert "commercial_property" in ruleset.rules["allowed_lobs"]

    rate_table = session.scalar(select(RateTable).where(RateTable.version == 1))
    assert rate_table is not None
    assert rate_table.rules["base_rate_permille"] == "0.5"


def test_alembic_at_head(session: Session) -> None:
    """The real migrations ran to head — the alembic_version table pins the latest revision (0003)."""
    from sqlalchemy import text

    versions = list(session.execute(text("SELECT version_num FROM alembic_version")).scalars())
    assert versions == ["0003_bind"], f"expected DB at head 0003_bind, got {versions}"


def test_policy_number_unique_invariant(session: Session) -> None:
    """DB-level invariant: binding.policy_number is UNIQUE — Postgres rejects a duplicate."""
    _, binding = _intake_assess_quote_bind(session, tiv_eur=400_000_00)
    dup = Binding(
        submission_id="another-submission",
        quote_id="another-quote",
        policy_number=binding.policy_number,  # same number → must violate the unique constraint
        pas_policy_id="pas-dup",
        status="bound",
        event_published=False,
        bound_by=_ACTOR,
    )
    session.add(dup)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
