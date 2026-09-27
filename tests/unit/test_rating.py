"""Pure unit tests for the rating engine (no DB, no network)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.rating.engine import (
    Adjustment,
    QuoteBreakdown,
    RateTableSpec,
    RatingError,
    RatingFacts,
    rate,
)
from tests.fixtures.submissions import V1_RATE_SPEC


def _facts(**overrides: object) -> RatingFacts:
    base: dict = {
        "tiv_eur": 500_000_00,  # €500,000 in eurocents
        "occupancy": "warehouse",
        "flags": frozenset(),
    }
    base.update(overrides)
    return RatingFacts(**base)  # type: ignore[arg-type]


def _sum_check(breakdown: QuoteBreakdown) -> None:
    """The final line item's running subtotal must equal the reported premium (reconciliation)."""
    assert breakdown.line_items[-1].running_subtotal_minor == breakdown.premium_minor


# --- base premium + occupancy factor ---------------------------------------


def test_base_premium_office_factor_1() -> None:
    # office factor 1.0: 0.5‰ × €500,000 × 1.0 = €250.00 = 25_000 eurocents
    breakdown = rate(_facts(occupancy="office"), V1_RATE_SPEC)
    assert breakdown.premium_minor == 25_000
    assert breakdown.currency == "EUR"
    assert breakdown.rate_table_version == 1
    _sum_check(breakdown)


def test_occupancy_factor_warehouse() -> None:
    # warehouse factor 1.25: 0.5‰ × €500,000 × 1.25 = €312.50 = 31_250 eurocents
    breakdown = rate(_facts(occupancy="warehouse"), V1_RATE_SPEC)
    assert breakdown.premium_minor == 31_250
    _sum_check(breakdown)


def test_occupancy_factor_light_manufacturing() -> None:
    # light_manufacturing factor 1.5: 25_000 × 1.5 = 37_500
    breakdown = rate(_facts(occupancy="light_manufacturing"), V1_RATE_SPEC)
    assert breakdown.premium_minor == 37_500
    _sum_check(breakdown)


def test_unknown_occupancy_raises() -> None:
    with pytest.raises(RatingError):
        rate(_facts(occupancy="volcano"), V1_RATE_SPEC)


# --- line-item shape --------------------------------------------------------


def test_breakdown_line_item_kinds_and_order_base_case() -> None:
    breakdown = rate(_facts(occupancy="office"), V1_RATE_SPEC)
    kinds = [li.kind for li in breakdown.line_items]
    labels = [li.label for li in breakdown.line_items]
    # base case (no gate flags set): just base + occupancy factor, in that order
    assert kinds == ["base", "factor"]
    assert labels == ["base_rate", "occupancy_factor:office"]


# --- loadings / discounts ---------------------------------------------------


def test_high_tiv_loading_applies() -> None:
    # €6,000,000 TIV → high_tiv flag. office factor 1.0.
    # base = 0.5‰ × €6,000,000 = €3,000.00 = 300_000 eurocents; ×1.10 = 330_000
    breakdown = rate(_facts(tiv_eur=6_000_000_00, occupancy="office", flags=frozenset({"high_tiv"})), V1_RATE_SPEC)
    assert breakdown.premium_minor == 330_000
    loading = [li for li in breakdown.line_items if li.kind == "loading"]
    assert len(loading) == 1
    assert loading[0].label == "high_tiv_loading"
    _sum_check(breakdown)


def test_sprinklered_discount_applies() -> None:
    # office 25_000 × 0.95 = 23_750
    breakdown = rate(_facts(occupancy="office", flags=frozenset({"sprinklered"})), V1_RATE_SPEC)
    assert breakdown.premium_minor == 23_750
    discount = [li for li in breakdown.line_items if li.kind == "discount"]
    assert len(discount) == 1
    assert discount[0].label == "sprinklered_discount"
    _sum_check(breakdown)


def test_adjustment_not_applied_when_flag_absent() -> None:
    # no flags → neither loading nor discount line items present
    breakdown = rate(_facts(occupancy="office"), V1_RATE_SPEC)
    assert all(li.kind not in {"loading", "discount"} for li in breakdown.line_items)


def test_ordering_loading_then_discount() -> None:
    # both flags: base 300_000 (€6M) ×1.10 = 330_000 ×0.95 = 313_500. Loading MUST precede discount.
    breakdown = rate(
        _facts(tiv_eur=6_000_000_00, occupancy="office", flags=frozenset({"high_tiv", "sprinklered"})),
        V1_RATE_SPEC,
    )
    assert breakdown.premium_minor == 313_500
    adj_labels = [li.label for li in breakdown.line_items if li.kind in {"loading", "discount"}]
    assert adj_labels == ["high_tiv_loading", "sprinklered_discount"]
    _sum_check(breakdown)


def test_adjustment_order_is_ratetable_order_not_flag_order() -> None:
    # A hand-built table where the discount is listed FIRST → it must be applied first regardless of flags.
    spec = RateTableSpec(
        version=9,
        base_rate_permille=Decimal("1.0"),
        occupancy_factors={"office": Decimal("1.0")},
        adjustments=(
            Adjustment("d", "discount", Decimal("0.5"), applies_when="a"),
            Adjustment("l", "loading", Decimal("2.0"), applies_when="b"),
        ),
    )
    breakdown = rate(RatingFacts(tiv_eur=1_000_000, occupancy="office", flags=frozenset({"a", "b"})), spec)
    order = [li.label for li in breakdown.line_items if li.kind in {"loading", "discount"}]
    assert order == ["d", "l"]


# --- rounding + reconciliation ----------------------------------------------


def test_rounding_happens_once_at_end_half_up() -> None:
    # Craft a fractional-cent intermediate: base 1.0‰ × 12_345 eurocents × 1.0 = 12.345 eurocents.
    # Rounded HALF_UP once → 12.
    spec = RateTableSpec(
        version=9,
        base_rate_permille=Decimal("1.0"),
        occupancy_factors={"office": Decimal("1.0")},
        adjustments=(),
    )
    breakdown = rate(RatingFacts(tiv_eur=12_345, occupancy="office", flags=frozenset()), spec)
    assert breakdown.premium_minor == 12
    _sum_check(breakdown)


def test_no_intermediate_rounding_error_accumulates() -> None:
    # A chain of adjustments on a fractional base must round only ONCE. Verify against a single
    # end-to-end Decimal computation.
    spec = RateTableSpec(
        version=9,
        base_rate_permille=Decimal("0.333"),
        occupancy_factors={"office": Decimal("1.07")},
        adjustments=(
            Adjustment("l", "loading", Decimal("1.13"), applies_when="a"),
            Adjustment("d", "discount", Decimal("0.91"), applies_when="a"),
        ),
    )
    facts = RatingFacts(tiv_eur=7_777_77, occupancy="office", flags=frozenset({"a"}))
    breakdown = rate(facts, spec)
    expected = Decimal("0.333") / 1000 * Decimal(7_777_77) * Decimal("1.07") * Decimal("1.13") * Decimal("0.91")
    from decimal import ROUND_HALF_UP

    assert breakdown.premium_minor == int(expected.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    _sum_check(breakdown)


def test_breakdown_line_items_sum_to_final_premium_full_chain() -> None:
    # warehouse + both flags on a €6M risk — every line item present, reconciles to premium_minor.
    breakdown = rate(
        _facts(tiv_eur=6_000_000_00, occupancy="warehouse", flags=frozenset({"high_tiv", "sprinklered"})),
        V1_RATE_SPEC,
    )
    kinds = [li.kind for li in breakdown.line_items]
    assert kinds == ["base", "factor", "loading", "discount"]
    _sum_check(breakdown)
