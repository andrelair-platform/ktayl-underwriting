"""The appetite/eligibility engine — a PURE, unit-testable assessment function (ADR-004).

`assess()` has no I/O and no DB: it takes plain value objects and returns an outcome + stable reason
codes. This is the seam that lets the rules be tested exhaustively and, later, versioned/audited
without touching persistence.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.enums import Outcome, ReasonCode


@dataclass(frozen=True)
class RulesetSpec:
    """The immutable rule payload (mirrors AppetiteRuleset.rules JSON), as a typed value object."""

    version: int
    allowed_lobs: frozenset[str]
    max_tiv_eur: int  # eurocents — accept up to (and including) this; refer above → committee seam (UW-03)
    excluded_occupancies: frozenset[str]
    sanctioned_countries: frozenset[str]

    @classmethod
    def from_rules(cls, version: int, rules: dict) -> RulesetSpec:
        return cls(
            version=version,
            allowed_lobs=frozenset(rules.get("allowed_lobs", [])),
            max_tiv_eur=int(rules["max_tiv_eur"]),
            excluded_occupancies=frozenset(rules.get("excluded_occupancies", [])),
            sanctioned_countries=frozenset(rules.get("sanctioned_countries", [])),
        )


@dataclass(frozen=True)
class SubmissionFacts:
    """The minimal, storage-free facts the engine needs from a submission."""

    line_of_business: str
    tiv_eur: int
    occupancy: str
    country: str


def assess(submission: SubmissionFacts, ruleset: RulesetSpec) -> tuple[Outcome, list[ReasonCode]]:
    """Evaluate a submission against a ruleset.

    Precedence: hard declines (sanction, excluded occupancy) first, then out-of-appetite LOB
    (refer), then the TIV authority band (refer above), else accept. Declines short-circuit —
    a sanctioned/excluded risk is never accepted regardless of TIV or LOB.
    """
    reasons: list[ReasonCode] = []

    # Hard declines take precedence.
    if submission.country.upper() in {c.upper() for c in ruleset.sanctioned_countries}:
        reasons.append(ReasonCode.SANCTIONED_COUNTRY)
    if submission.occupancy in ruleset.excluded_occupancies:
        reasons.append(ReasonCode.EXCLUDED_OCCUPANCY)
    if reasons:
        return Outcome.DECLINE, reasons

    # Refer conditions (LOB out of appetite, or above the TIV authority band → committee seam).
    if submission.line_of_business not in ruleset.allowed_lobs:
        reasons.append(ReasonCode.LOB_OUT_OF_APPETITE)
    if submission.tiv_eur > ruleset.max_tiv_eur:
        reasons.append(ReasonCode.TIV_ABOVE_AUTHORITY)
    if reasons:
        return Outcome.REFER, reasons

    return Outcome.ACCEPT, [ReasonCode.WITHIN_APPETITE]
