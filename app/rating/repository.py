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

# The v2 rate table (ADR-009 P1) = v1's loss-cost rules + the technical/commercial/tax loading stack.
# All figures are simulation, credible-but-indicative (Pricing & Portfolio governance guideline):
#   expense_loading 15% (acquisition+admin) · risk_margin 6% (cost of capital) · cat_provision 4%
#   commercial adjustment authorised band ±15% ([0.85, 1.15]) · IPT 9% (indicative TCA) · €50 policy fee.
# Immutable + versioned (ADR-004): v2 is a NEW row; current() returns it so new quotes price fully-loaded.
V2_RULES: dict = {
    **V1_RULES,
    "expense_loading": "0.15",
    "risk_margin": "0.06",
    "cat_provision": "0.04",
    "commercial_adjustment_min": "0.85",
    "commercial_adjustment_max": "1.15",
    "ipt_rate": "0.09",
    "fixed_fees_minor": 5000,
}

# The v3 rate table (ADR-010) = v2 + the deterministic actuarial completeness: experience rating + deductible
# credits + limit/ILF factors. Simulation, credible-but-indicative (Pricing & Portfolio governance guideline):
#   experience: benchmark LR 60% · √-rule full-credibility at €500k earned premium · swing band [0.75, 1.40]
#   deductible credits: ≥€10k −2.5% · ≥€50k −5% · ≥€250k −10% · ≥€1M −17.5% (retained layer → lower loss cost)
#   ILF: ≤€1M 0.70 · ≤€5M 0.85 · ≤€20M 0.95 · ≤€100M 1.0 (a limited layer prices below full value)
# Immutable + versioned (ADR-004): v3 is a NEW row; current() returns it so new quotes price fully-complete.
V3_RULES: dict = {
    **V2_RULES,
    "expected_loss_ratio": "0.60",
    "full_credibility_premium_minor": 50000000,  # €500,000 earned premium → credibility Z = 1
    "experience_swing_min": "0.75",
    "experience_swing_max": "1.40",
    "deductible_credits": [
        {"min_deductible_minor": 1000000, "factor": "0.975"},  # ≥ €10k retention
        {"min_deductible_minor": 5000000, "factor": "0.95"},  # ≥ €50k
        {"min_deductible_minor": 25000000, "factor": "0.90"},  # ≥ €250k
        {"min_deductible_minor": 100000000, "factor": "0.825"},  # ≥ €1M
    ],
    "limit_factors": [
        {"max_limit_minor": 100000000, "factor": "0.70"},  # ≤ €1M limit
        {"max_limit_minor": 500000000, "factor": "0.85"},  # ≤ €5M
        {"max_limit_minor": 2000000000, "factor": "0.95"},  # ≤ €20M
        {"max_limit_minor": 10000000000, "factor": "1.0"},  # ≤ €100M (≈ full value)
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
        pure_premium_minor: int | None = None,
        technical_premium_minor: int | None = None,
        commercial_premium_minor: int | None = None,
        taxes_minor: int | None = None,
        facts: dict | None = None,
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
        pure_premium_minor: int | None = None,
        technical_premium_minor: int | None = None,
        commercial_premium_minor: int | None = None,
        taxes_minor: int | None = None,
        facts: dict | None = None,
    ) -> Quote:
        quote = Quote(
            submission_id=submission_id,
            premium_minor=premium_minor,
            currency=currency,
            rate_table_version=rate_table_version,
            breakdown=breakdown,
            created_by=created_by,
            pure_premium_minor=pure_premium_minor,
            technical_premium_minor=technical_premium_minor,
            commercial_premium_minor=commercial_premium_minor,
            taxes_minor=taxes_minor,
            facts=facts,
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


def seed_v2(session: Session) -> RateTable:
    """Install rate table version 2 (ADR-009 P1 loading stack) if absent. Idempotent.

    Requires v1 first (seed_v1). Once present, `current()` returns v2, so new quotes price with the
    full technical/commercial/tax build-up. Never edits v1 (ADR-004 immutability)."""
    repo = SqlRateTableRepository(session)
    existing = repo.get_version(2)
    if existing is not None:
        return existing
    rate_table = repo.create_version(version=2, rules=V2_RULES)
    session.commit()
    return rate_table


def seed_v3(session: Session) -> RateTable:
    """Install rate table version 3 (ADR-010 experience rating + deductible/limit credits) if absent.
    Idempotent. Requires v2. Once present, `current()` returns v3, so new quotes price with the complete
    deterministic build-up. Never edits v1/v2 (ADR-004 immutability)."""
    repo = SqlRateTableRepository(session)
    existing = repo.get_version(3)
    if existing is not None:
        return existing
    rate_table = repo.create_version(version=3, rules=V3_RULES)
    session.commit()
    return rate_table
