"""AppetiteRuleset — a versioned, immutable ruleset (ADR-004).

Immutability is enforced by convention + the repository: a change never edits a row in place;
it inserts a new version row. The rule payload is stored as JSON so a ruleset is self-describing
and auditable. Money thresholds (max_tiv_eur) are eurocents (minor units).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

# JSON works on both Postgres and SQLite via the generic type; variant kept explicit for clarity.
JsonType = JSON().with_variant(SQLITE_JSON(), "sqlite")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class AppetiteRuleset(Base):
    """An immutable, versioned appetite ruleset. Never updated in place — a new version is a new row."""

    __tablename__ = "appetite_ruleset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    # rule payload: {allowed_lobs, max_tiv_eur, excluded_occupancies, sanctioned_countries}
    rules: Mapped[dict] = mapped_column(JsonType, nullable=False)
