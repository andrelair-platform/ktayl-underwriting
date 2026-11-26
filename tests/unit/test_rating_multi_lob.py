"""Pure unit tests for Marine & Engineering pricing (the per-LOB rate tables, reusing the shared engine)."""

from __future__ import annotations

import pytest

from app.rating.engine import RateTableSpec, RatingError, RatingFacts, rate
from app.rating.repository import ENGINEERING_RULES, MARINE_RULES

MARINE_SPEC = RateTableSpec.from_rules(4, MARINE_RULES)
ENG_SPEC = RateTableSpec.from_rules(5, ENGINEERING_RULES)


def _facts(occupancy: str, tiv_eur: int = 1_000_000_00) -> RatingFacts:
    return RatingFacts(tiv_eur=tiv_eur, occupancy=occupancy, flags=frozenset())


def _reconciles(breakdown) -> None:
    assert breakdown.line_items[-1].running_subtotal_minor == breakdown.premium_minor


# --- Marine ---------------------------------------------------------------------------------------


def test_marine_prices_a_cargo_risk_and_reconciles() -> None:
    bd = rate(_facts("cargo_general"), MARINE_SPEC)
    assert bd.premium_minor > 0
    assert bd.rate_table_version == 4
    assert bd.currency == "EUR"
    _reconciles(bd)


def test_marine_class_factor_orders_premium() -> None:
    # hazardous (1.8) > general (1.0) > hull (0.8), same sum insured + loading stack.
    hazardous = rate(_facts("cargo_hazardous"), MARINE_SPEC).premium_minor
    general = rate(_facts("cargo_general"), MARINE_SPEC).premium_minor
    hull = rate(_facts("hull"), MARINE_SPEC).premium_minor
    assert hazardous > general > hull


def test_marine_base_rate_is_higher_than_commercial_property() -> None:
    # Marine's technical base (1.2‰) is richer than property (0.5‰) — a marine cargo_general risk at the same
    # neutral factor prices above a property office risk (factor 1.0) of the same sum insured.
    from tests.fixtures.submissions import V1_RATE_SPEC

    marine = rate(_facts("cargo_general"), MARINE_SPEC).premium_minor
    property_office = rate(_facts("office"), V1_RATE_SPEC).premium_minor
    assert marine > property_office


# --- Engineering ----------------------------------------------------------------------------------


def test_engineering_prices_works_and_reconciles() -> None:
    bd = rate(_facts("contract_works"), ENG_SPEC)
    assert bd.premium_minor > 0
    assert bd.rate_table_version == 5
    _reconciles(bd)


def test_engineering_erection_is_dearer_than_contract_works() -> None:
    erection = rate(_facts("erection_works"), ENG_SPEC).premium_minor  # factor 1.2
    contract = rate(_facts("contract_works"), ENG_SPEC).premium_minor  # factor 1.0
    machinery = rate(_facts("machinery_breakdown"), ENG_SPEC).premium_minor  # factor 0.7
    assert erection > contract > machinery


# --- the class must exist in the LOB's factor map -------------------------------------------------


def test_a_property_occupancy_is_not_a_valid_marine_class() -> None:
    # 'office' is a property occupancy; it is not in the marine factor map → RatingError (not a silent 0).
    with pytest.raises(RatingError):
        rate(_facts("office"), MARINE_SPEC)
