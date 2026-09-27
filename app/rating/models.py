"""Rating persistence — a versioned, immutable RateTable (ADR-004) + a persisted Quote.

Immutability of the rate table is enforced by convention + the repository: a change never edits a
row in place; it inserts a new version row. The rule payload is stored as JSON so a rate table is
self-describing and auditable — exactly like AppetiteRuleset. Money (premium_minor) is eurocents.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.appetite.models import JsonType
from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class RateTable(Base):
    """An immutable, versioned rate table. Never updated in place — a new version is a new row."""

    __tablename__ = "rate_table"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    # rule payload: {base_rate_permille, occupancy_factors, adjustments}
    rules: Mapped[dict] = mapped_column(JsonType, nullable=False)


class Quote(Base):
    """A priced quote for a submission. Re-quoting inserts a new row; the latest (max id/created_at) wins."""

    __tablename__ = "quote"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    submission_id: Mapped[str] = mapped_column(String(36), ForeignKey("submission.id"), nullable=False, index=True)
    premium_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)  # eurocents (minor units)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    rate_table_version: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdown: Mapped[list] = mapped_column(JsonType, nullable=False)  # ordered list of line-item dicts
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
