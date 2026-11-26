"""AppetiteRuleset repository — interface (Protocol) + SQLAlchemy impl.

Enforces immutability: there is no update method; `create_version` only ever inserts. The v1 seed
ruleset is defined here and installed by `seed_v1` if no ruleset exists yet (idempotent).
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.appetite.models import AppetiteRuleset
from app.appetite.rules import RulesetSpec
from app.enums import LineOfBusiness, Occupancy

# The v1 seed ruleset (ADR-004). Money is eurocents: €10,000,000 = 1_000_000_000 eurocents.
V1_RULES: dict = {
    "allowed_lobs": [LineOfBusiness.COMMERCIAL_PROPERTY.value],
    "max_tiv_eur": 1_000_000_000,
    "excluded_occupancies": [Occupancy.FIREWORKS_MANUFACTURING.value],
    "sanctioned_countries": ["KP", "IR", "SY", "RU"],
}

# The v2 ruleset — opens Marine + Engineering appetite (the per-LOB pricing extension). Both now have rate
# tables, so a submission for them flows appetite → rate → quote instead of being referred out-of-appetite.
# Immutable + versioned (ADR-004): v2 is a NEW row; current() returns it. TIV authority band + the excluded
# occupancy + sanctions carry over unchanged.
V2_RULES: dict = {
    **V1_RULES,
    "allowed_lobs": [
        LineOfBusiness.COMMERCIAL_PROPERTY.value,
        LineOfBusiness.MARINE.value,
        LineOfBusiness.ENGINEERING.value,
    ],
}


class AppetiteRepository(Protocol):
    """Read the current ruleset + append new immutable versions."""

    def current(self) -> AppetiteRuleset | None: ...

    def get_version(self, version: int) -> AppetiteRuleset | None: ...

    def create_version(self, version: int, rules: dict) -> AppetiteRuleset: ...


class SqlAppetiteRepository:
    """SQLAlchemy-backed, append-only implementation (ADR-004: never edit in place)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def current(self) -> AppetiteRuleset | None:
        return self._session.scalar(select(AppetiteRuleset).order_by(desc(AppetiteRuleset.version)).limit(1))

    def get_version(self, version: int) -> AppetiteRuleset | None:
        return self._session.scalar(select(AppetiteRuleset).where(AppetiteRuleset.version == version))

    def create_version(self, version: int, rules: dict) -> AppetiteRuleset:
        ruleset = AppetiteRuleset(version=version, rules=rules)
        self._session.add(ruleset)
        self._session.flush()
        return ruleset


def spec_of(ruleset: AppetiteRuleset) -> RulesetSpec:
    """Build the pure engine value object from a persisted ruleset row."""
    return RulesetSpec.from_rules(ruleset.version, ruleset.rules)


def seed_v1(session: Session) -> AppetiteRuleset:
    """Install version 1 if no ruleset exists yet. Idempotent — safe to call on every startup."""
    repo = SqlAppetiteRepository(session)
    existing = repo.current()
    if existing is not None:
        return existing
    ruleset = repo.create_version(version=1, rules=V1_RULES)
    session.commit()
    return ruleset


def seed_v2(session: Session) -> AppetiteRuleset:
    """Install version 2 (opens Marine + Engineering appetite) if absent. Idempotent; requires v1. Once
    present, current() returns v2, so those LOBs are in appetite. Never edits v1 (ADR-004 immutability)."""
    repo = SqlAppetiteRepository(session)
    existing = repo.get_version(2)
    if existing is not None:
        return existing
    ruleset = repo.create_version(version=2, rules=V2_RULES)
    session.commit()
    return ruleset
