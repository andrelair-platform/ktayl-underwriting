"""SQLAlchemy 2.x declarative base + engine/session wiring.

Column types are deliberately generic (String, BigInteger, JSON, DateTime) so the same models run
on PostgreSQL (prod) and SQLite in-memory (L1 tests) with no dialect-specific types. Money is
BigInteger (eurocents, minor units) per the platform convention.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_settings = get_settings()
# future=True is the default in 2.x; pool_pre_ping guards against stale Postgres connections.
engine = create_engine(_settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped DB session (overridden in tests)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
