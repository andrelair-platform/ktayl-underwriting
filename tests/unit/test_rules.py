"""Pure unit tests for the appetite engine (no DB, no network)."""

from __future__ import annotations

from app.appetite.rules import RulesetSpec, SubmissionFacts, assess
from app.enums import Outcome, ReasonCode
from tests.fixtures.submissions import V1_SPEC


def _facts(**overrides: object) -> SubmissionFacts:
    base = {
        "line_of_business": "commercial_property",
        "tiv_eur": 500_000_00,
        "occupancy": "warehouse",
        "country": "FR",
    }
    base.update(overrides)
    return SubmissionFacts(**base)  # type: ignore[arg-type]


def test_within_appetite_accepts() -> None:
    outcome, reasons = assess(_facts(), V1_SPEC)
    assert outcome is Outcome.ACCEPT
    assert reasons == [ReasonCode.WITHIN_APPETITE]


def test_tiv_at_authority_band_boundary_accepts() -> None:
    # exactly at the max is within authority (accept up to and including)
    outcome, reasons = assess(_facts(tiv_eur=1_000_000_000), V1_SPEC)
    assert outcome is Outcome.ACCEPT
    assert reasons == [ReasonCode.WITHIN_APPETITE]


def test_tiv_above_authority_refers() -> None:
    outcome, reasons = assess(_facts(tiv_eur=1_000_000_001), V1_SPEC)
    assert outcome is Outcome.REFER
    assert reasons == [ReasonCode.TIV_ABOVE_AUTHORITY]


def test_lob_out_of_appetite_refers() -> None:
    outcome, reasons = assess(_facts(line_of_business="marine"), V1_SPEC)
    assert outcome is Outcome.REFER
    assert reasons == [ReasonCode.LOB_OUT_OF_APPETITE]


def test_multiple_refer_reasons_are_collected() -> None:
    outcome, reasons = assess(_facts(line_of_business="marine", tiv_eur=2_000_000_000), V1_SPEC)
    assert outcome is Outcome.REFER
    assert set(reasons) == {ReasonCode.LOB_OUT_OF_APPETITE, ReasonCode.TIV_ABOVE_AUTHORITY}


def test_excluded_occupancy_declines() -> None:
    outcome, reasons = assess(_facts(occupancy="fireworks_manufacturing"), V1_SPEC)
    assert outcome is Outcome.DECLINE
    assert reasons == [ReasonCode.EXCLUDED_OCCUPANCY]


def test_sanctioned_country_declines() -> None:
    outcome, reasons = assess(_facts(country="KP"), V1_SPEC)
    assert outcome is Outcome.DECLINE
    assert reasons == [ReasonCode.SANCTIONED_COUNTRY]


def test_sanctioned_country_is_case_insensitive() -> None:
    outcome, reasons = assess(_facts(country="ir"), V1_SPEC)
    assert outcome is Outcome.DECLINE
    assert reasons == [ReasonCode.SANCTIONED_COUNTRY]


def test_decline_takes_precedence_over_refer() -> None:
    # excluded occupancy + above authority + wrong LOB → still a decline (hard rules short-circuit)
    outcome, reasons = assess(
        _facts(occupancy="fireworks_manufacturing", line_of_business="marine", tiv_eur=9_000_000_000),
        V1_SPEC,
    )
    assert outcome is Outcome.DECLINE
    assert ReasonCode.EXCLUDED_OCCUPANCY in reasons
    assert ReasonCode.LOB_OUT_OF_APPETITE not in reasons


def test_both_hard_declines_collected() -> None:
    outcome, reasons = assess(_facts(occupancy="fireworks_manufacturing", country="RU"), V1_SPEC)
    assert outcome is Outcome.DECLINE
    assert set(reasons) == {ReasonCode.SANCTIONED_COUNTRY, ReasonCode.EXCLUDED_OCCUPANCY}


def test_spec_from_rules_roundtrip() -> None:
    spec = RulesetSpec.from_rules(
        7,
        {
            "allowed_lobs": ["commercial_property", "marine"],
            "max_tiv_eur": 42,
            "excluded_occupancies": ["x"],
            "sanctioned_countries": ["ZZ"],
        },
    )
    assert spec.version == 7
    assert spec.allowed_lobs == frozenset({"commercial_property", "marine"})
    assert spec.max_tiv_eur == 42
