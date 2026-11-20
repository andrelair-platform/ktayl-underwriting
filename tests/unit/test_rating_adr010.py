"""Pure unit tests for ADR-010 — deterministic actuarial completeness: experience rating +
deductible/limit credits. No DB, no network. Uses the v3 rate table + the v2 table to prove
backward compatibility (a v2 table ignores the new facts → prices exactly as before).

Reference risk: office, TIV €500,000 → base loss cost = 0.5‰ × €500,000 × occupancy(office 1.0) = €250
(25_000 minor). Each ADR-010 step multiplies that loss cost before the technical loadings.
"""

from __future__ import annotations

from decimal import Decimal

from app.rating.engine import RateTableSpec, RatingFacts, rate
from app.rating.repository import V2_RULES, V3_RULES

V2_SPEC = RateTableSpec.from_rules(2, V2_RULES)
V3_SPEC = RateTableSpec.from_rules(3, V3_RULES)

BASE_LOSS_COST = 25_000  # 0.5‰ × €500,000 × 1.0 (office), eurocents


def _facts(**overrides: object) -> RatingFacts:
    base: dict = {"tiv_eur": 500_000_00, "occupancy": "office", "flags": frozenset()}
    base.update(overrides)
    return RatingFacts(**base)  # type: ignore[arg-type]


def _line(bd, label):
    return next((li for li in bd.line_items if li.label == label), None)


# ── deductible credit ─────────────────────────────────────────────────────────────────────────
def test_deductible_credit_applies_band_factor() -> None:
    # €50k deductible → the "≥ €50k" band → factor 0.95
    bd = rate(_facts(deductible_eur=5_000_000), V3_SPEC)
    assert bd.pure_premium_minor == round(BASE_LOSS_COST * 0.95)  # 23_750
    assert _line(bd, "deductible_credit") is not None


def test_bigger_deductible_earns_bigger_credit() -> None:
    small = rate(_facts(deductible_eur=1_000_000), V3_SPEC).pure_premium_minor  # ≥€10k → 0.975
    big = rate(_facts(deductible_eur=100_000_000), V3_SPEC).pure_premium_minor  # ≥€1M → 0.825
    assert big < small < BASE_LOSS_COST


def test_no_deductible_is_neutral() -> None:
    bd = rate(_facts(), V3_SPEC)
    assert bd.pure_premium_minor == BASE_LOSS_COST
    assert _line(bd, "deductible_credit") is None


# ── limit / ILF factor ────────────────────────────────────────────────────────────────────────
def test_limit_factor_applies_ilf() -> None:
    # €1M limit → the "≤ €1M" band → factor 0.70 (a limited layer prices below full value)
    bd = rate(_facts(limit_eur=100_000_000), V3_SPEC)
    assert bd.pure_premium_minor == round(BASE_LOSS_COST * 0.70)  # 17_500
    assert _line(bd, "limit_factor") is not None


def test_higher_limit_costs_more() -> None:
    low = rate(_facts(limit_eur=100_000_000), V3_SPEC).pure_premium_minor  # ≤€1M → 0.70
    high = rate(_facts(limit_eur=2_000_000_000), V3_SPEC).pure_premium_minor  # ≤€20M → 0.95
    assert low < high <= BASE_LOSS_COST


def test_full_value_is_neutral() -> None:
    bd = rate(_facts(limit_eur=0), V3_SPEC)  # 0 = full value
    assert bd.pure_premium_minor == BASE_LOSS_COST
    assert _line(bd, "limit_factor") is None


# ── experience rating (credibility-blended) ────────────────────────────────────────────────────
def test_good_loss_history_earns_a_credit() -> None:
    # €500k prior premium → Z=1 (full credibility); actual LR 0.48 vs expected 0.60 → mod 0.80
    bd = rate(_facts(prior_premium_eur=50_000_000, prior_losses_eur=24_000_000), V3_SPEC)
    assert bd.pure_premium_minor == round(BASE_LOSS_COST * 0.80)  # 20_000
    exp = _line(bd, "experience_modifier")
    assert exp is not None and exp.kind == "discount"


def test_bad_loss_history_loads_up_to_the_swing_cap() -> None:
    # actual LR 1.08 vs 0.60 → raw 1.8 → clamped to the +40% swing cap
    bd = rate(_facts(prior_premium_eur=50_000_000, prior_losses_eur=54_000_000), V3_SPEC)
    assert bd.pure_premium_minor == round(BASE_LOSS_COST * 1.40)  # 35_000
    exp = _line(bd, "experience_modifier")
    assert exp is not None and exp.kind == "loading"


def test_partial_credibility_blends_toward_neutral() -> None:
    # €125k prior premium → Z = √0.25 = 0.5; actual LR 0.30 → raw = 0.5·0.5 + 0.5·1 = 0.75 (floor)
    bd = rate(_facts(prior_premium_eur=12_500_000, prior_losses_eur=3_750_000), V3_SPEC)
    assert bd.pure_premium_minor == round(BASE_LOSS_COST * 0.75)


def test_no_loss_history_is_neutral() -> None:
    bd = rate(_facts(), V3_SPEC)
    assert _line(bd, "experience_modifier") is None
    assert bd.pure_premium_minor == BASE_LOSS_COST


# ── composition + backward compatibility ───────────────────────────────────────────────────────
def test_all_three_components_compose_in_order() -> None:
    bd = rate(
        _facts(
            deductible_eur=5_000_000,
            limit_eur=2_000_000_000,
            prior_premium_eur=50_000_000,
            prior_losses_eur=24_000_000,
        ),
        V3_SPEC,
    )
    # loss cost × deductible(0.95) × limit(0.95) × experience(0.80)
    expected = Decimal(BASE_LOSS_COST) * Decimal("0.95") * Decimal("0.95") * Decimal("0.80")
    assert bd.pure_premium_minor == round(expected)
    labels = [li.label for li in bd.line_items]
    assert labels.index("deductible_credit") < labels.index("limit_factor") < labels.index("experience_modifier")


def test_v2_table_ignores_the_new_facts_backward_compatible() -> None:
    # Same rich facts, but a v2 rate table has no ADR-010 config → every new step is neutral.
    rich = _facts(
        deductible_eur=100_000_000,
        limit_eur=100_000_000,
        prior_premium_eur=50_000_000,
        prior_losses_eur=5_000_000,
    )
    bd = rate(rich, V2_SPEC)
    assert bd.pure_premium_minor == BASE_LOSS_COST  # unchanged from the plain v2 price
    for label in ("deductible_credit", "limit_factor", "experience_modifier"):
        assert _line(bd, label) is None
