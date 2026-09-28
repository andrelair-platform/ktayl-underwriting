"""The rating engine — a PURE, unit-testable pricing function (ADR-004, mirrors appetite/rules.py).

`rate()` has no I/O and no DB: it takes plain value objects and returns an explainable
`QuoteBreakdown`. This is the seam that lets the pricing be tested exhaustively and, later,
versioned/audited without touching persistence.

Money is eurocents (int, minor units). Computation is done in a high-precision intermediate and
rounded ONCE at the end so the final premium and the breakdown line items reconcile exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


class RatingError(Exception):
    """Raised when the facts cannot be priced against the rate table (e.g. unknown occupancy)."""


@dataclass(frozen=True)
class Adjustment:
    """A named, ordered loading (kind='loading') or discount (kind='discount').

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
    """The immutable rate-table payload (mirrors RateTable.rules JSON), as a typed value object."""

    version: int
    base_rate_permille: Decimal  # premium rate per mille (‰) of TIV
    occupancy_factors: dict[str, Decimal]
    adjustments: tuple[Adjustment, ...]  # ordered loadings/discounts

    @classmethod
    def from_rules(cls, version: int, rules: dict) -> RateTableSpec:
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
        )


@dataclass(frozen=True)
class RatingFacts:
    """The minimal, storage-free facts the engine needs from a submission."""

    tiv_eur: int  # eurocents (minor units)
    occupancy: str
    flags: frozenset[str]  # boolean input flags that gate loadings/discounts (derived from submission)


@dataclass(frozen=True)
class LineItem:
    """One explainable step in the premium build-up.

    kind ∈ {base, factor, loading, discount}. `value` is the human-legible driver of the step
    (a per-mille base rate, a factor multiplier, or an adjustment multiplier) as a string.
    `running_subtotal_minor` is the premium in eurocents after this step (rounded for display).
    """

    label: str
    kind: str
    value: str
    running_subtotal_minor: int


@dataclass(frozen=True)
class QuoteBreakdown:
    """The explainable result of pricing: an ordered line-item trail + the final premium (eurocents)."""

    rate_table_version: int
    premium_minor: int
    currency: str
    line_items: tuple[LineItem, ...]


def _to_minor(amount: Decimal) -> int:
    """Round a eurocents Decimal to a whole integer (minor unit) once, half-up."""
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def rate(facts: RatingFacts, rate_table: RateTableSpec) -> QuoteBreakdown:
    """Price a risk against a rate table into an explainable, reconciling breakdown.

    technical premium = base_rate_permille/1000 × tiv_eur × occupancy_factor, then the ordered
    loadings/discounts are applied in sequence. All arithmetic runs on a high-precision Decimal
    subtotal; each line item's `running_subtotal_minor` is that subtotal rounded for display, and
    the final `premium_minor` is the same subtotal rounded once at the end — so the trail is legible
    and the last line item equals the final premium.
    """
    occupancy_factor = rate_table.occupancy_factors.get(facts.occupancy)
    if occupancy_factor is None:
        raise RatingError(f"no occupancy factor for {facts.occupancy!r} in rate table v{rate_table.version}")

    items: list[LineItem] = []

    # Base: the technical premium before occupancy + adjustments = base_rate‰ × TIV.
    subtotal = rate_table.base_rate_permille / Decimal(1000) * Decimal(facts.tiv_eur)
    items.append(
        LineItem(
            label="base_rate",
            kind="base",
            value=f"{rate_table.base_rate_permille}‰ of TIV",
            running_subtotal_minor=_to_minor(subtotal),
        )
    )

    # Occupancy factor.
    subtotal = subtotal * occupancy_factor
    items.append(
        LineItem(
            label=f"occupancy_factor:{facts.occupancy}",
            kind="factor",
            value=f"×{occupancy_factor}",
            running_subtotal_minor=_to_minor(subtotal),
        )
    )

    # Ordered loadings/discounts — only those whose gate flag is set (or ungated) apply.
    for adj in rate_table.adjustments:
        if adj.applies_when is not None and adj.applies_when not in facts.flags:
            continue
        subtotal = subtotal * adj.factor
        items.append(
            LineItem(
                label=adj.name,
                kind=adj.kind,
                value=f"×{adj.factor}",
                running_subtotal_minor=_to_minor(subtotal),
            )
        )

    premium_minor = _to_minor(subtotal)
    return QuoteBreakdown(
        rate_table_version=rate_table.version,
        premium_minor=premium_minor,
        currency="EUR",
        line_items=tuple(items),
    )
