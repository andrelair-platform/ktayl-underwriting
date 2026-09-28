"""Submission use-cases — the thin orchestration layer over the domain modules.

Keeps the routers dumb: intake, assess (run the pure engine + persist Decision + append audit),
and the two reads. All persistence goes through the repositories/session passed in.
"""

from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.appetite.repository import AppetiteRepository, spec_of
from app.appetite.rules import SubmissionFacts, assess
from app.audit.repository import AuditRepository
from app.bind.models import Binding
from app.decision.models import Decision
from app.entity.repository import CounterpartyRepository
from app.enums import Outcome
from app.submission.models import Submission
from app.submission.schemas import SubmissionCreate, SubmissionListItem


class SubmissionNotFoundError(Exception):
    """Raised when a submission id does not exist."""


class NoRulesetError(Exception):
    """Raised when no appetite ruleset is available to assess against."""


def create_submission(
    session: Session,
    payload: SubmissionCreate,
    counterparties: CounterpartyRepository,
    audit: AuditRepository,
    actor: str,
) -> Submission:
    """Intake: create the (local) counterparty + the submission, and append an audit entry."""
    cp = counterparties.add(name=payload.counterparty.name, country=payload.counterparty.country)
    submission = Submission(
        counterparty_id=cp.id,
        line_of_business=payload.line_of_business.value,
        tiv_eur=payload.tiv_eur,
        occupancy=payload.occupancy.value,
        country=payload.country.upper(),
        postcode=payload.postcode,
        requested_cover=payload.requested_cover,
        broker_ref=payload.broker_ref,
    )
    session.add(submission)
    session.flush()
    audit.append(
        submission_id=submission.id,
        action="submission.created",
        actor=actor,
        detail={"line_of_business": submission.line_of_business, "tiv_eur": submission.tiv_eur},
    )
    session.commit()
    session.refresh(submission)
    return submission


def get_submission(session: Session, submission_id: str) -> Submission:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise SubmissionNotFoundError(submission_id)
    return submission


def latest_decision(session: Session, submission_id: str) -> Decision | None:
    return session.scalar(
        select(Decision).where(Decision.submission_id == submission_id).order_by(desc(Decision.decided_at)).limit(1)
    )


def list_submissions(
    session: Session, *, outcome: Outcome | None = None, limit: int = 50, offset: int = 0
) -> list[SubmissionListItem]:
    """The workbench inbox: submissions (newest first) with their latest appetite outcome + bound flag.

    `decision` is append-only history, so the "latest" decision per submission is the one with the
    greatest `decided_at` (a subquery groups by submission and takes the max). `outcome`, when given,
    filters to submissions whose LATEST decision has that outcome — so triaging "refer" shows exactly
    the referrals awaiting a human.
    """
    latest = (
        select(Decision.submission_id, func.max(Decision.decided_at).label("m"))
        .group_by(Decision.submission_id)
        .subquery()
    )
    stmt = (
        select(Submission, Decision)
        .outerjoin(latest, latest.c.submission_id == Submission.id)
        .outerjoin(
            Decision,
            (Decision.submission_id == Submission.id) & (Decision.decided_at == latest.c.m),
        )
        .order_by(desc(Submission.created_at))
    )
    if outcome is not None:
        stmt = stmt.where(Decision.outcome == outcome.value)
    rows = session.execute(stmt.limit(limit).offset(offset)).all()

    ids = [submission.id for submission, _ in rows]
    bound_ids: set[str] = set()
    if ids:
        bound_ids = set(session.scalars(select(Binding.submission_id).where(Binding.submission_id.in_(ids))).all())

    items: list[SubmissionListItem] = []
    for submission, decision in rows:
        item = SubmissionListItem.model_validate(submission)
        item.latest_outcome = Outcome(decision.outcome) if decision is not None else None
        item.bound = submission.id in bound_ids
        items.append(item)
    return items


def assess_submission(
    session: Session,
    submission_id: str,
    appetite: AppetiteRepository,
    audit: AuditRepository,
    actor: str,
) -> Decision:
    """Run the appetite engine against the current ruleset, persist the Decision + an audit entry.

    `decision` rows are **append-only history**: each assess INSERTS a new Decision (never an update),
    and reads use "latest wins" (`latest_decision`). This is intentional — it preserves the full
    negotiation/re-assessment trail (an auditor can see every decision a submission ever got), not a
    bug. No row is ever mutated or deleted.
    """
    submission = get_submission(session, submission_id)

    ruleset = appetite.current()
    if ruleset is None:
        raise NoRulesetError()

    facts = SubmissionFacts(
        line_of_business=submission.line_of_business,
        tiv_eur=submission.tiv_eur,
        occupancy=submission.occupancy,
        country=submission.country,
    )
    outcome, reason_codes = assess(facts, spec_of(ruleset))

    decision = Decision(
        submission_id=submission.id,
        outcome=outcome.value,
        reason_codes=[c.value for c in reason_codes],
        appetite_version=ruleset.version,
        decided_by=actor,
    )
    session.add(decision)
    session.flush()

    audit.append(
        submission_id=submission.id,
        action="submission.assessed",
        actor=actor,
        ruleset_version=ruleset.version,
        outcome=outcome.value,
        detail={"reason_codes": [c.value for c in reason_codes]},
    )
    session.commit()
    session.refresh(decision)
    return decision
