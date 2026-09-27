"""Test fixtures. L1 runs with NO Docker/network: the API tests use a SQLite in-memory DB with the
DB dependency overridden; the appetite engine tests are pure and need no fixtures here.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Import models so all tables register on Base.metadata before create_all.
from app.appetite import models as _appetite_models  # noqa: F401
from app.audit import models as _audit_models  # noqa: F401
from app.db.base import Base, get_db
from app.decision import models as _decision_models  # noqa: F401
from app.entity import models as _entity_models  # noqa: F401
from app.submission import models as _submission_models  # noqa: F401


@pytest.fixture
def db_session(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    # StaticPool + a shared in-memory connection so every session sees the same schema/data.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    # Point the app's lifespan seed (which uses SessionLocal) at the in-memory engine so no Postgres
    # connection is ever attempted during startup.
    import app.main as app_main

    monkeypatch.setattr(app_main, "SessionLocal", testing_session)

    # Disable the startup DB-wait + alembic migration: L1 runs with no Postgres and builds the schema
    # in-memory via Base.metadata.create_all above (not via Alembic). Flip the gate off on the cached
    # settings object so the lifespan skips bootstrap_database().
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "run_db_migrations_on_startup", False)

    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    from app.main import create_app

    app = create_app()

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # TestClient as a context manager runs the lifespan (which seeds appetite ruleset v1 against the
    # monkeypatched in-memory SessionLocal).
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
