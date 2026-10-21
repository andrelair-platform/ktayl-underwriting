"""Pure unit tests for the ADR-009 P1 staged build-up (loss cost → technical → commercial → taxes).

No DB, no network. Uses the v2 rate table (the loading stack) + hand-built specs for edge cases.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.rating.engine import RateTableSpec, RatingError, RatingFacts, rate
from app.rating.repository import V2_RULES

V2_SPEC = RateTableSpec.from_rules(2, V2_RULES)


def _facts(**overrides: object) -> RatingFacts:
    base: dict = {"tiv_eur": 500_000_00, "occupancy": "office", "flags": frozenset()}
    base.update(overrides)
    return RatingFacts(**base)  # type: ignore[arg-type]


def _round(d: Decimal) -> int:
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# --- the full staged build-up (office €500k, neutral commercial adjustment) --------------------


def test_v2_full_build_up_office() -> None:
    bd = rate(_facts(occupancy="office"), V2_SPEC)
    # loss cost: 0.5‰ × €500,000 × 1.0 = €250.00
    assert bd.pure_premium_minor == 25_000
    # technical: × (1.15 · 1.06 · 1.04)
    tech = Decimal(25_000) * Decimal("1.15") * Decimal("1.06") * Decimal("1.04")
    assert bd.technical_premium_minor == _round(tech)
    # commercial: adjustment neutral (1.0) → unchanged
    assert bd.commercial_premium_minor == _round(tech)
    # taxes: + €50 fee + 9% IPT on the commercial premium
    final = tech + Decimal(5000) + tech * Decimal("0.09")
    assert bd.premium_minor == _round(final)
    assert bd.taxes_minor == bd.premium_minor - bd.commercial_premium_minor
    # ordering is pure < technical < commercial(=technical) < final
    assert bd.pure_premium_minor < bd.technical_premium_minor < bd.premium_minor


def test_v2_stages_and_kinds() -> None:
    bd = rate(_facts(occupancy="office"), V2_SPEC)
    stages = [(li.stage, li.kind, li.label) for li in bd.line_items]
    assert stages == [
        ("loss_cost", "base", "base_rate"),
        ("loss_cost", "factor", "occupancy_factor:office"),
        ("technical", "loading", "expense_loading"),
        ("technical", "loading", "risk_margin"),
        ("technical", "loading", "cat_provision"),
        ("taxes", "fee", "policy_fee"),
        ("taxes", "tax", "ipt"),
    ]
    # no commercial line when the adjustment is neutral
    assert all(li.stage != "commercial" for li in bd.line_items)


def test_v2_last_line_item_reconciles_to_final_premium() -> None:
    bd = rate(_facts(occupancy="warehouse", flags=frozenset({"sprinklered"})), V2_SPEC)
    assert bd.line_items[-1].running_subtotal_minor == bd.premium_minor
    assert bd.line_items[-1].stage == "taxes"


def test_v2_risk_adjustments_are_in_loss_cost_stage() -> None:
    # high_tiv + sprinklered are RISK modifiers → loss-cost stage, before technical loadings.
    bd = rate(_facts(tiv_eur=6_000_000_00, occupancy="office", flags=frozenset({"high_tiv", "sprinklered"})), V2_SPEC)
    loss_cost = [li.label for li in bd.line_items if li.stage == "loss_cost"]
    assert "high_tiv_loading" in loss_cost and "sprinklered_discount" in loss_cost
    # pure premium reflects the risk adjustments; technical builds on top of it
    assert bd.technical_premium_minor > bd.pure_premium_minor


# --- commercial adjustment (bounded) ----------------------------------------------------------


def test_commercial_adjustment_within_band_applies_and_is_a_line_item() -> None:
    bd = rate(_facts(occupancy="office", commercial_adjustment=Decimal("0.90")), V2_SPEC)
    comm = [li for li in bd.line_items if li.stage == "commercial"]
    assert len(comm) == 1 and comm[0].kind == "discount" and comm[0].label == "commercial_adjustment"
    tech = Decimal(bd.technical_premium_minor)
    # commercial subtotal is technical × 0.90 (computed on the precise Decimal, verified on the rounded one)
    assert bd.commercial_premium_minor <= bd.technical_premium_minor
    assert bd.commercial_premium_minor == _round(
        Decimal(25_000) * Decimal("1.15") * Decimal("1.06") * Decimal("1.04") * Decimal("0.90")
    )
    assert tech  # technical unchanged by the commercial stage


def test_commercial_adjustment_loading_above_one() -> None:
    bd = rate(_facts(occupancy="office", commercial_adjustment=Decimal("1.10")), V2_SPEC)
    comm = [li for li in bd.line_items if li.stage == "commercial"]
    assert len(comm) == 1 and comm[0].kind == "loading"
    assert bd.commercial_premium_minor > bd.technical_premium_minor


def test_commercial_adjustment_out_of_band_raises() -> None:
    # band is [0.85, 1.15]; 0.50 is below → referral, not a bad price
    with pytest.raises(RatingError):
        rate(_facts(occupancy="office", commercial_adjustment=Decimal("0.50")), V2_SPEC)
    with pytest.raises(RatingError):
        rate(_facts(occupancy="office", commercial_adjustment=Decimal("1.50")), V2_SPEC)


def test_commercial_adjustment_at_band_edge_is_allowed() -> None:
    # inclusive band edges
    assert rate(_facts(occupancy="office", commercial_adjustment=Decimal("0.85")), V2_SPEC)
    assert rate(_facts(occupancy="office", commercial_adjustment=Decimal("1.15")), V2_SPEC)


# --- backward compatibility (a v1-shaped spec has neutral loadings) ---------------------------


def test_v1_shaped_spec_has_no_extra_stages_and_pure_equals_final() -> None:
    v1_like = RateTableSpec(
        version=1,
        base_rate_permille=Decimal("0.5"),
        occupancy_factors={"office": Decimal("1.0")},
        adjustments=(),
    )
    bd = rate(_facts(occupancy="office"), v1_like)
    assert bd.premium_minor == bd.pure_premium_minor == bd.technical_premium_minor == bd.commercial_premium_minor
    assert bd.taxes_minor == 0
    assert all(li.stage == "loss_cost" for li in bd.line_items)
