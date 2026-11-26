"""DB-backed tests for the per-LOB rate-table selection + the Marine/Engineering seeds + appetite opening."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.appetite.repository import SqlAppetiteRepository, spec_of
from app.appetite.repository import seed_v1 as seed_appetite_v1
from app.appetite.repository import seed_v2 as seed_appetite_v2
from app.appetite.rules import SubmissionFacts, assess
from app.enums import LineOfBusiness, Outcome
from app.rating.repository import (
    SqlRateTableRepository,
    seed_engineering,
    seed_marine,
    seed_v1,
    seed_v2,
    seed_v3,
)

_CP = LineOfBusiness.COMMERCIAL_PROPERTY.value
_MARINE = LineOfBusiness.MARINE.value
_ENG = LineOfBusiness.ENGINEERING.value


def _seed_all_rate_tables(db_session: Session) -> SqlRateTableRepository:
    seed_v1(db_session)
    seed_v2(db_session)
    seed_v3(db_session)
    seed_marine(db_session)
    seed_engineering(db_session)
    return SqlRateTableRepository(db_session)


def test_current_selects_the_rate_table_per_lob(db_session: Session) -> None:
    repo = _seed_all_rate_tables(db_session)
    # Commercial property still resolves to v3 — NOT the max version (marine v4 / engineering v5).
    assert repo.current(_CP).version == 3
    assert repo.current().version == 3  # default LOB = commercial property
    assert repo.current(_MARINE).version == 4
    assert repo.current(_ENG).version == 5
    # each carries its LOB tag (property rows are untagged → treated as property)
    assert repo.current(_MARINE).rules["line_of_business"] == _MARINE
    assert repo.current(_ENG).rules["line_of_business"] == _ENG
    assert "line_of_business" not in repo.current(_CP).rules


def test_lob_seeds_are_idempotent(db_session: Session) -> None:
    _seed_all_rate_tables(db_session)
    before = len(SqlRateTableRepository(db_session).list_versions())
    seed_marine(db_session)
    seed_engineering(db_session)  # re-run
    after = len(SqlRateTableRepository(db_session).list_versions())
    assert before == after  # no duplicate rows


def test_appetite_v2_opens_marine_and_engineering(db_session: Session) -> None:
    seed_appetite_v1(db_session)
    seed_appetite_v2(db_session)
    ruleset = spec_of(SqlAppetiteRepository(db_session).current())
    for lob in (_CP, _MARINE, _ENG):
        facts = SubmissionFacts(
            line_of_business=lob, occupancy="cargo_general" if lob == _MARINE else "office",
            tiv_eur=500_000_00, country="FR",
        )
        outcome, _ = assess(facts, ruleset)
        assert outcome != Outcome.DECLINE, f"{lob} should be in appetite"
