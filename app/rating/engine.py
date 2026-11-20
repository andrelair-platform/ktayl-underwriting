"""The rating engine — a PURE, unit-testable pricing function (ADR-004 + ADR-009).

`rate()` has no I/O and no DB: it takes plain value objects and returns an explainable
`QuoteBreakdown`. This is the seam that lets the pricing be tested exhaustively and, later,
versioned/audited without touching persistence.

**ADR-009 P1 — the staged build-up (loss cost → technical → commercial → taxes).** The premium is
built in named stages, each `LineItem` tagged by `stage`, and the subtotals at each stage boundary are
reported so a quote is actuarially legible:

    LOSS COST (pure premium)   base_rate‰/1000 × TIV × occupancy_factor × risk adjustments
    + technical loadings        expense loading · risk/capital margin · CAT provision   (multiplicative)
    = TECHNICAL PREMIUM
    × commercial adjustment     bounded (rate-table min/max), default neutral 1.0
    = COMMERCIAL PREMIUM
    + taxes/fees                policy fee (additive) + IPT (on the commercial premium)
    = FINAL QUOTED PREMIUM

**Backward compatible:** a rate table with no loading params (v1) leaves every added stage neutral —
expense/risk/CAT = 0, commercial adjustment = 1, IPT/fees = 0 — so it emits no extra line items and the
final premium equals the pure premium (the pre-ADR-009 behaviour).

Money is eurocents (int, minor units). Computation runs on a high-precision `Decimal` subtotal and is
rounded ONCE at the end, so the final premium and the last breakdown line item reconcile exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

_ONE = Decimal(1)
_ZERO = Decimal(0)


class RatingError(Exception):
    """Raised when the facts cannot be priced against the rate table (unknown occupancy, or a
    commercial adjustment outside the rate table's authorised band → a referral, not a bad price)."""


@dataclass(frozen=True)
class Adjustment:
    """A named, ordered RISK loading (kind='loading') or discount (kind='discount') in the loss-cost stage.

    `factor` is a multiplier applied to the running subtotal: 1.10 = +10% loading, 0.95 = -5% discount.
    `applies_when` names the boolean input flag (from `RatingFacts.flags`) that gates it; None = always.

    Note: the flags are set by the caller (app/rating/service.py::_facts_of). The high-TIV loading's
    gate ("high_tiv") is a **strict `>` €5,000,000** boundary — the loading does NOT apply at exactly
    €5M. That is an intentional band edge (same convention as the appetite TIV authority band), not a
    bug; the engine here just applies whatever flags it is handed.
    """

    name: str
    kind: str  # "loading" | "discount"
    factor: Decimal
    applies_when: str | None = None


@dataclass(frozen=True)
class RateTableSpec:
    """The immutable rate-table payload (mirrors RateTable.rules JSON), as a typed value object.

    The ADR-009 P1 loading parameters all **default to neutral** so a v1 rate table (which omits them)
    prices exactly as before. Percentages are decimals (0.15 = 15%); `fixed_fees_minor` is eurocents.
    """

    version: int
    base_rate_permille: Decimal  # premium rate per mille (‰) of TIV
    occupancy_factors: dict[str, Decimal]
    adjustments: tuple[Adjustment, ...]  # ordered risk loadings/discounts (loss-cost stage)
    # --- ADR-009 P1 loading stack (neutral by default) ---
    expense_loading: Decimal = _ZERO  # acquisition + admin, ×(1+pct) on the pure premium
    risk_margin: Decimal = _ZERO  # cost of capital / volatility, ×(1+pct)
    cat_provision: Decimal = _ZERO  # catastrophe provision, ×(1+pct)
    commercial_adjustment_min: Decimal = _ONE  # authorised band for the per-quote commercial adjustment
    commercial_adjustment_max: Decimal = _ONE
    ipt_rate: Decimal = _ZERO  # insurance premium tax, on the commercial premium
    fixed_fees_minor: int = 0  # flat policy fee (eurocents), additive
    # --- ADR-010 deterministic actuarial completeness (all neutral by default → v1/v2 price unchanged) ---
    expected_loss_ratio: Decimal = _ZERO  # benchmark LR for experience rating; 0 = experience rating OFF
    full_credibility_premium_minor: int = 0  # prior premium for full credibility (Z=1, √-rule); 0 = OFF
    experience_swing_min: Decimal = Decimal("0.5")  # clamp on the experience modifier (sane default)
    experience_swing_max: Decimal = Decimal("2")
    deductible_credits: tuple[tuple[int, Decimal], ...] = ()  # (min_deductible_minor, factor≤1) bands, any order
    limit_factors: tuple[tuple[int, Decimal], ...] = ()  # (max_limit_minor, factor) ILF bands, any order

    @classmethod
    def from_rules(cls, version: int, rules: dict) -> RateTableSpec:
        def dec(key: str, default: str) -> Decimal:
            return Decimal(str(rules.get(key, default)))

        return cls(
            version=version,
            base_rate_permille=Decimal(str(rules["base_rate_permille"])),
            occupancy_factors={k: Decimal(str(v)) for k, v in rules["occupancy_factors"].items()},
            adjustments=tuple(
                Adjustment(
                    name=a["name"],
                    kind=a["kind"],
                    factor=Decimal(str(a["factor"])),
                    applies_when=a.get("applies_when"),
                )
                for a in rules.get("adjustments", [])
            ),
            expense_loading=dec("expense_loading", "0"),
            risk_margin=dec("risk_margin", "0"),
            cat_provision=dec("cat_provision", "0"),
            commercial_adjustment_min=dec("commercial_adjustment_min", "1"),
            commercial_adjustment_max=dec("commercial_adjustment_max", "1"),
            ipt_rate=dec("ipt_rate", "0"),
            fixed_fees_minor=int(rules.get("fixed_fees_minor", 0)),
            expected_loss_ratio=dec("expected_loss_ratio", "0"),
            full_credibility_premium_minor=int(rules.get("full_credibility_premium_minor", 0)),
            experience_swing_min=dec("experience_swing_min", "0.5"),
            experience_swing_max=dec("experience_swing_max", "2"),
            deductible_credits=tuple(
                (int(b["min_deductible_minor"]), Decimal(str(b["factor"]))) for b in rules.get("deductible_credits", [])
            ),
            limit_factors=tuple(
                (int(b["max_limit_minor"]), Decimal(str(b["factor"]))) for b in rules.get("limit_factors", [])
            ),
        )


@dataclass(frozen=True)
class RatingFacts:
    """The minimal, storage-free facts the engine needs from a submission."""

    tiv_eur: int  # eurocents (minor units)
    occupancy: str
    flags: frozenset[str]  # boolean input flags that gate loadings/discounts (derived from submission)
    commercial_adjustment: Decimal = _ONE  # underwriter judgement (bounded); neutral by default
    # --- ADR-010 inputs (0 = absent → the corresponding step is neutral) ---
    deductible_eur: int = 0  # the insured's retention (eurocents); bigger → bigger credit
    limit_eur: int = 0  # the policy limit (eurocents); 0 = full value (no ILF)
    prior_premium_eur: int = 0  # experience-period earned premium (eurocents); drives credibility
    prior_losses_eur: int = 0  # experience-period incurred losses (eurocents)


@dataclass(frozen=True)
class LineItem:
    """One explainable step in the premium build-up.

    `stage` ∈ {loss_cost, technical, commercial, taxes}. `kind` ∈ {base, factor, loading, discount,
    fee, tax}. `value` is the human-legible driver of the step (a per-mille base rate, a factor/
    adjustment multiplier, or an additive amount) as a string. `running_subtotal_minor` is the premium
    in eurocents after this step (rounded for display).
    """

    label: str
    kind: str
    value: str
    running_subtotal_minor: int
    stage: str = "loss_cost"


@dataclass(frozen=True)
class QuoteBreakdown:
    """The explainable result of pricing: the ordered line-item trail, the staged subtotals, and the
    final premium (all eurocents). `premium_minor` is the final quoted premium (incl. taxes/fees)."""

    rate_table_version: int
    premium_minor: int
    currency: str
    line_items: tuple[LineItem, ...]
    pure_premium_minor: int = 0  # loss cost
    technical_premium_minor: int = 0  # pure + expense + risk margin + CAT
    commercial_premium_minor: int = 0  # technical × commercial adjustment
    taxes_minor: int = 0  # fees + IPT (= premium_minor − commercial_premium_minor)


def _to_minor(amount: Decimal) -> int:
    """Round a eurocents Decimal to a whole integer (minor unit) once, half-up."""
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _deductible_factor(deductible_eur: int, bands: tuple[tuple[int, Decimal], ...]) -> Decimal:
    """ADR-010 — the deductible credit: the factor of the HIGHEST band whose `min_deductible` ≤ the deductible
    (a bigger retention earns a bigger credit). Neutral (×1) when there's no deductible or no bands."""
    if deductible_eur <= 0 or not bands:
        return _ONE
    factor = _ONE
    for min_ded, f in sorted(bands):
        if deductible_eur >= min_ded:
            factor = f
    return factor


def _limit_factor(limit_eur: int, bands: tuple[tuple[int, Decimal], ...]) -> Decimal:
    """ADR-010 — the limit/ILF factor: the factor of the SMALLEST band whose `max_limit` ≥ the limit (above the
    top band → the top factor). Neutral (×1) at full value (no limit) or no bands."""
    if limit_eur <= 0 or not bands:
        return _ONE
    ordered = sorted(bands)
    for max_lim, f in ordered:
        if limit_eur <= max_lim:
            return f
    return ordered[-1][1]


def _experience_mod(facts: RatingFacts, rate_table: RateTableSpec) -> Decimal:
    """ADR-010 — the credibility-blended experience modifier:
        mod = clamp( Z·(actual_LR / expected_LR) + (1 − Z), swing_min, swing_max )
    with Z = min(1, √(prior_premium / full_credibility_premium)) (the square-root partial-credibility rule).
    Neutral (×1) when experience rating is off (no `expected_loss_ratio` / `full_credibility_premium`) or the
    account has no prior-premium history."""
    if (
        rate_table.expected_loss_ratio <= _ZERO
        or rate_table.full_credibility_premium_minor <= 0
        or facts.prior_premium_eur <= 0
    ):
        return _ONE
    actual_lr = Decimal(facts.prior_losses_eur) / Decimal(facts.prior_premium_eur)
    z = (Decimal(facts.prior_premium_eur) / Decimal(rate_table.full_credibility_premium_minor)).sqrt()
    if z > _ONE:
        z = _ONE
    raw = z * (actual_lr / rate_table.expected_loss_ratio) + (_ONE - z)
    if raw < rate_table.experience_swing_min:
        return rate_table.experience_swing_min
    if raw > rate_table.experience_swing_max:
        return rate_table.experience_swing_max
    return raw


def rate(facts: RatingFacts, rate_table: RateTableSpec) -> QuoteBreakdown:
    """Price a risk against a rate table into an explainable, reconciling, staged breakdown (ADR-009 P1).

    All arithmetic runs on a high-precision Decimal subtotal; each line item's `running_subtotal_minor`
    is that subtotal rounded for display, and the final `premium_minor` is the subtotal rounded once at
    the end — so the trail is legible and the last line item equals the final premium. Neutral loading
    params (a v1 table) produce no extra line items and `premium_minor == pure_premium_minor`.
    """
    occupancy_factor = rate_table.occupancy_factors.get(facts.occupancy)
    if occupancy_factor is None:
        raise RatingError(f"no occupancy factor for {facts.occupancy!r} in rate table v{rate_table.version}")

    items: list[LineItem] = []

    # ── LOSS COST (pure premium) ──────────────────────────────────────────────
    subtotal = rate_table.base_rate_permille / Decimal(1000) * Decimal(facts.tiv_eur)
    items.append(
        LineItem(
            "base_rate", "base", f"{rate_table.base_rate_permille}‰ of TIV", _to_minor(subtotal), stage="loss_cost"
        )
    )

    subtotal = subtotal * occupancy_factor
    items.append(
        LineItem(
            f"occupancy_factor:{facts.occupancy}",
            "factor",
            f"×{occupancy_factor}",
            _to_minor(subtotal),
            stage="loss_cost",
        )
    )

    for adj in rate_table.adjustments:  # ordered risk loadings/discounts, gated by flags
        if adj.applies_when is not None and adj.applies_when not in facts.flags:
            continue
        subtotal = subtotal * adj.factor
        items.append(LineItem(adj.name, adj.kind, f"×{adj.factor}", _to_minor(subtotal), stage="loss_cost"))

    # ── ADR-010 — deterministic actuarial completeness (loss-cost stage; neutral steps add no line item) ──
    ded_factor = _deductible_factor(facts.deductible_eur, rate_table.deductible_credits)
    if ded_factor != _ONE:  # the insured retains a layer → lower loss cost → a credit
        subtotal = subtotal * ded_factor
        items.append(
            LineItem("deductible_credit", "discount", f"×{ded_factor}", _to_minor(subtotal), stage="loss_cost")
        )

    lim_factor = _limit_factor(facts.limit_eur, rate_table.limit_factors)
    if lim_factor != _ONE:  # increased-limit factor (ILF) on a limited layer
        kind = "discount" if lim_factor < _ONE else "loading"
        subtotal = subtotal * lim_factor
        items.append(LineItem("limit_factor", kind, f"×{lim_factor}", _to_minor(subtotal), stage="loss_cost"))

    exp_mod = _experience_mod(facts, rate_table)
    if exp_mod != _ONE:  # the account's own loss experience, credibility-blended with the book rate
        kind = "discount" if exp_mod < _ONE else "loading"
        subtotal = subtotal * exp_mod
        items.append(LineItem("experience_modifier", kind, f"×{exp_mod}", _to_minor(subtotal), stage="loss_cost"))

    pure_premium_minor = _to_minor(subtotal)

    # ── TECHNICAL PREMIUM (pure + expense + risk margin + CAT) ────────────────
    for name, pct in (
        ("expense_loading", rate_table.expense_loading),
        ("risk_margin", rate_table.risk_margin),
        ("cat_provision", rate_table.cat_provision),
    ):
        if pct > _ZERO:
            subtotal = subtotal * (_ONE + pct)
            items.append(LineItem(name, "loading", f"×{_ONE + pct}", _to_minor(subtotal), stage="technical"))

    technical_premium_minor = _to_minor(subtotal)

    # ── COMMERCIAL PREMIUM (technical × bounded commercial adjustment) ────────
    cadj = facts.commercial_adjustment
    if cadj != _ONE:
        if cadj < rate_table.commercial_adjustment_min or cadj > rate_table.commercial_adjustment_max:
            raise RatingError(
                f"commercial adjustment {cadj} outside the authorised band "
                f"[{rate_table.commercial_adjustment_min}, {rate_table.commercial_adjustment_max}] "
                f"(rate table v{rate_table.version}) — refer to the CUO"
            )
        subtotal = subtotal * cadj
        kind = "discount" if cadj < _ONE else "loading"
        items.append(LineItem("commercial_adjustment", kind, f"×{cadj}", _to_minor(subtotal), stage="commercial"))

    commercial_premium_minor = _to_minor(subtotal)
    commercial_precise = subtotal  # IPT is levied on the commercial premium (pre-fee)

    # ── TAXES / FEES (additive) ───────────────────────────────────────────────
    if rate_table.fixed_fees_minor > 0:
        subtotal = subtotal + Decimal(rate_table.fixed_fees_minor)
        items.append(
            LineItem("policy_fee", "fee", f"+{rate_table.fixed_fees_minor} minor", _to_minor(subtotal), stage="taxes")
        )
    if rate_table.ipt_rate > _ZERO:
        ipt = commercial_precise * rate_table.ipt_rate
        subtotal = subtotal + ipt
        items.append(
            LineItem(
                "ipt", "tax", f"+{rate_table.ipt_rate * 100}% of commercial premium", _to_minor(subtotal), stage="taxes"
            )
        )

    premium_minor = _to_minor(subtotal)
    return QuoteBreakdown(
        rate_table_version=rate_table.version,
        premium_minor=premium_minor,
        currency="EUR",
        line_items=tuple(items),
        pure_premium_minor=pure_premium_minor,
        technical_premium_minor=technical_premium_minor,
        commercial_premium_minor=commercial_premium_minor,
        taxes_minor=premium_minor - commercial_premium_minor,
    )
