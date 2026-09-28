"""Rating use-cases — the thin orchestration layer for quoting a submission.

Keeps the router dumb: quote (guard on the latest decision → run the pure engine → persist Quote +
append audit) and the read. All persistence goes through the repositories/session passed in.

The engine's boolean input flags are DERIVED from fields the submission already has — no new
submission columns are invented:
  - "high_tiv"    : tiv_eur above the rate-table's high-TIV threshold.
  - "sprinklered" : the requested cover text mentions a sprinkler (a simple, explainable heuristic
                    standing in for a structured fire-protection field a richer intake would carry).
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session

from app.audit.repository import AuditRepository
from app.enums import Outcome
from app.rating.engine import RatingFacts, rate
from app.rating.models import Quote
from app.rating.repository import HIGH_TIV_THRESHOLD_EUR, QuoteRepository, RateTableRepository, spec_of
from app.submission import service as submission_service
from app.submission.models import Submission


class NoRateTableError(Exception):
    """Raised when no rate table is available to price against."""


class NoDecisionError(Exception):
    """Raised when the submission has not been assessed yet (no decision to gate the quote)."""


class DeclinedRiskError(Exception):
    """Raised when the latest decision is a decline — a declined risk must not be quoted."""


def _facts_of(submission: Submission) -> RatingFacts:
    """Derive the engine facts (incl. gate flags) from existing submission fields only."""
    flags: set[str] = set()
    if submission.tiv_eur > HIGH_TIV_THRESHOLD_EUR:
        flags.add("high_tiv")
    if "sprinkler" in submission.requested_cover.lower():
        flags.add("sprinklered")
    return RatingFacts(tiv_eur=submission.tiv_eur, occupancy=submission.occupancy, flags=frozenset(flags))


def quote_submission(
    session: Session,
    submission_id: str,
    rate_tables: RateTableRepository,
    quotes: QuoteRepository,
    audit: AuditRepository,
    actor: str,
) -> Quote:
    """Guard on the latest decision, run the rating engine against the current rate table, persist.

    `quote` rows are **append-only history**: each call INSERTS a new Quote (never an update) and reads
    use "latest wins" (`latest_quote`). This is intentional negotiation/re-quote history — an auditor
    can see every price a submission was ever offered — not a bug. No row is mutated or deleted.

    Raises SubmissionNotFoundError / NoDecisionError (→ 404), DeclinedRiskError (→ 409),
    NoRateTableError (→ 503).
    """
    submission = submission_service.get_submission(session, submission_id)

    decision = submission_service.latest_decision(session, submission_id)
    if decision is None:
        raise NoDecisionError(submission_id)
    if decision.outcome == Outcome.DECLINE.value:
        raise DeclinedRiskError(submission_id)

    rate_table = rate_tables.current()
    if rate_table is None:
        raise NoRateTableError()

    breakdown = rate(_facts_of(submission), spec_of(rate_table))
    breakdown_json = [asdict(item) for item in breakdown.line_items]

    quote = quotes.add(
        submission_id=submission.id,
        premium_minor=breakdown.premium_minor,
        currency=breakdown.currency,
        rate_table_version=breakdown.rate_table_version,
        breakdown=breakdown_json,
        created_by=actor,
    )

    audit.append(
        submission_id=submission.id,
        action="quote",
        actor=actor,
        ruleset_version=rate_table.version,
        detail={"premium_minor": breakdown.premium_minor, "currency": breakdown.currency},
    )
    session.commit()
    session.refresh(quote)
    return quote


def latest_quote(session: Session, submission_id: str, quotes: QuoteRepository) -> Quote | None:
    return quotes.latest_for_submission(submission_id)
