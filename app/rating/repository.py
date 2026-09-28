"""Rating repositories — interfaces (Protocol) + SQLAlchemy impls.

The RateTable repository enforces immutability: there is no update method; `create_version` only ever
inserts (ADR-004). The v1 seed rate table is defined here and installed by `seed_v1` if none exists
yet (idempotent). The Quote repository is append + read only: re-quoting inserts a new row and the
latest one wins.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.enums import Occupancy
from app.rating.engine import RateTableSpec
from app.rating.models import Quote, RateTable

# The v1 seed rate table (ADR-004), commercial_property only.
#   base_rate_permille : 0.5‰ of TIV (the technical base rate).
#   occupancy_factors  : multiplier per occupancy — riskier activity, higher factor.
#   adjustments        : ordered, named loadings/discounts. Each is gated by an input flag derived
#                        from existing submission fields (no new submission columns invented):
#                          high_tiv_loading   +10% when TIV > €5,000,000 (flag "high_tiv"; strict
#                                             `>` — NOT applied at exactly €5M, an intentional boundary)
#                          sprinklered_discount -5% for a sprinklered risk (flag "sprinklered")
V1_RULES: dict = {
    "base_rate_permille": "0.5",
    "occupancy_factors": {
        Occupancy.OFFICE.value: "1.0",
        Occupancy.RETAIL.value: "1.1",
        Occupancy.WAREHOUSE.value: "1.25",
        Occupancy.LIGHT_MANUFACTURING.value: "1.5",
        Occupancy.FIREWORKS_MANUFACTURING.value: "3.0",
    },
    "adjustments": [
        {"name": "high_tiv_loading", "kind": "loading", "factor": "1.10", "applies_when": "high_tiv"},
        {"name": "sprinklered_discount", "kind": "discount", "factor": "0.95", "applies_when": "sprinklered"},
    ],
}

# TIV (eurocents) above which the high_tiv_loading applies — €5,000,000. The band is **strict `>`**:
# a risk at EXACTLY €5,000,000 is NOT loaded (the loading applies only above it). This is an
# intentional boundary, matching the appetite TIV authority-band convention (accepted at the
# boundary, referred/loaded only beyond it) — see app/rating/service.py::_facts_of.
HIGH_TIV_THRESHOLD_EUR = 500_000_000


class RateTableRepository(Protocol):
    """Read the current rate table + append new immutable versions."""

    def current(self) -> RateTable | None: ...

    def get_version(self, version: int) -> RateTable | None: ...

    def list_versions(self) -> list[RateTable]: ...

    def create_version(self, version: int, rules: dict) -> RateTable: ...


class SqlRateTableRepository:
    """SQLAlchemy-backed, append-only implementation (ADR-004: never edit in place)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def current(self) -> RateTable | None:
        return self._session.scalar(select(RateTable).order_by(desc(RateTable.version)).limit(1))

    def get_version(self, version: int) -> RateTable | None:
        return self._session.scalar(select(RateTable).where(RateTable.version == version))

    def list_versions(self) -> list[RateTable]:
        return list(self._session.scalars(select(RateTable).order_by(desc(RateTable.version))))

    def create_version(self, version: int, rules: dict) -> RateTable:
        rate_table = RateTable(version=version, rules=rules)
        self._session.add(rate_table)
        self._session.flush()
        return rate_table


class QuoteRepository(Protocol):
    """Persist quotes + read the latest per submission."""

    def add(
        self,
        submission_id: str,
        premium_minor: int,
        currency: str,
        rate_table_version: int,
        breakdown: list,
        created_by: str,
    ) -> Quote: ...

    def latest_for_submission(self, submission_id: str) -> Quote | None: ...


class SqlQuoteRepository:
    """SQLAlchemy-backed quote store — insert + read-latest (append-only)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        submission_id: str,
        premium_minor: int,
        currency: str,
        rate_table_version: int,
        breakdown: list,
        created_by: str,
    ) -> Quote:
        quote = Quote(
            submission_id=submission_id,
            premium_minor=premium_minor,
            currency=currency,
            rate_table_version=rate_table_version,
            breakdown=breakdown,
            created_by=created_by,
        )
        self._session.add(quote)
        self._session.flush()
        return quote

    def latest_for_submission(self, submission_id: str) -> Quote | None:
        # Latest = max created_at then id (a stable tie-break for same-instant re-quotes).
        return self._session.scalar(
            select(Quote)
            .where(Quote.submission_id == submission_id)
            .order_by(desc(Quote.created_at), desc(Quote.id))
            .limit(1)
        )


def spec_of(rate_table: RateTable) -> RateTableSpec:
    """Build the pure engine value object from a persisted rate-table row."""
    return RateTableSpec.from_rules(rate_table.version, rate_table.rules)


def seed_v1(session: Session) -> RateTable:
    """Install rate table version 1 if none exists yet. Idempotent — safe to call on every startup."""
    repo = SqlRateTableRepository(session)
    existing = repo.current()
    if existing is not None:
        return existing
    rate_table = repo.create_version(version=1, rules=V1_RULES)
    session.commit()
    return rate_table
