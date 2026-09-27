"""Bind use-cases — orchestrate the PAS 3-step lifecycle + emit the bound-risk event (ADR-006).

Keeps the router dumb: guard (accepted decision + a quote must exist) → derive a deterministic
policy_number → create → submit → activate against the live policy service → record the Binding →
append audit → publish the bound-risk event (best-effort). All external effects sit behind interfaces
(PolicyServiceClient / BoundRiskPublisher / TokenProvider) injected by the caller, so L1 runs with no
network.

Idempotency has three layers (ADR-006):
  1. **Deterministic policy_number** — ``policy_number_for(quote_id)`` is a pure, stable hash, so a
     retry targets the same PAS policy and the same UW Binding row.
  2. **409-on-create → success** — the PAS returns 409 for a duplicate policy_number; the client
     resolves the existing id and the flow continues (activate is idempotent).
  3. **Existing-Binding no-op** — if a Binding already exists for the submission, bind returns it with
     no PAS calls and no duplicate event.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.audit.repository import AuditRepository
from app.bind.models import Binding
from app.bind.policy_client import (
    CreatePolicyRequest,
    PolicyAlreadyExistsError,
    PolicyServiceClient,
)
from app.bind.publisher import BoundRiskPublisher
from app.bind.repository import BindingRepository
from app.enums import LineOfBusiness, Outcome
from app.rating.repository import QuoteRepository
from app.submission import service as submission_service
from app.submission.models import Submission

logger = logging.getLogger(__name__)

# Default cover period when the submission carries no explicit dates (thin v1 intake): today → +1y.
_DEFAULT_TERM_DAYS = 365

# LOB → PAS product_code. A simple explicit mapping (a richer catalogue would live in MDM/#20 later).
_PRODUCT_CODE_BY_LOB: dict[str, str] = {
    LineOfBusiness.COMMERCIAL_PROPERTY.value: "COMM_PROP",
    LineOfBusiness.MARINE.value: "MARINE",
    LineOfBusiness.ENGINEERING.value: "ENGINEERING",
    LineOfBusiness.FINANCIAL_LINES.value: "FIN_LINES",
}


class NoAcceptedDecisionError(Exception):
    """Raised when the latest decision is not ``accept`` — only accepted risks bind in v1 (→ 422)."""


class NoQuoteError(Exception):
    """Raised when the submission has no quote to bind (→ 422)."""


def policy_number_for(quote_id: str) -> str:
    """Deterministic, stable policy_number derived from the quote id (ADR-006 idempotency).

    Pure: same quote id → same number. A short uppercase hex slice of a SHA-1 keeps it readable and
    collision-safe enough for a v1 identifier.
    """
    digest = hashlib.sha1(quote_id.encode("utf-8")).hexdigest()[:12].upper()
    return f"UW-{digest}"


def _product_code_for(line_of_business: str) -> str:
    return _PRODUCT_CODE_BY_LOB.get(line_of_business, line_of_business.upper())


def _cover_dates() -> tuple[str, str]:
    """Effective/expiry ISO dates. v1 assumption: effective = today, expiry = +1 year (the thin
    submission intake carries no cover dates yet)."""
    effective: date = datetime.now(UTC).date()
    expiry = effective + timedelta(days=_DEFAULT_TERM_DAYS)
    return effective.isoformat(), expiry.isoformat()


def _create_request(submission: Submission, counterparty_name: str, policy_number: str) -> CreatePolicyRequest:
    """Map a UW submission → the thin PAS CreatePolicyRequest (ADR-006)."""
    effective_date, expiry_date = _cover_dates()
    return CreatePolicyRequest(
        policy_number=policy_number,
        holder_name=counterparty_name,
        product_code=_product_code_for(submission.line_of_business),
        effective_date=effective_date,
        expiry_date=expiry_date,
    )


def bind_submission(
    session: Session,
    submission_id: str,
    bindings: BindingRepository,
    quotes: QuoteRepository,
    audit: AuditRepository,
    policy_client: PolicyServiceClient,
    publisher: BoundRiskPublisher,
    actor: str,
) -> Binding:
    """Guard → (idempotent) create→submit→activate in the PAS → record Binding + audit → publish.

    Raises SubmissionNotFoundError (→ 404), NoAcceptedDecisionError / NoQuoteError (→ 422).
    """
    submission = submission_service.get_submission(session, submission_id)

    # Idempotent re-bind: an existing binding short-circuits — no PAS calls, no duplicate event.
    existing = bindings.by_submission(submission_id)
    if existing is not None:
        return existing

    decision = submission_service.latest_decision(session, submission_id)
    if decision is None or decision.outcome != Outcome.ACCEPT.value:
        raise NoAcceptedDecisionError(submission_id)

    quote = quotes.latest_for_submission(submission_id)
    if quote is None:
        raise NoQuoteError(submission_id)

    counterparty_name = _counterparty_name(session, submission)
    policy_number = policy_number_for(quote.id)

    # 409-on-create is treated as success inside the client (resolves the existing id). If the id
    # can't be resolved AND we have no local Binding, fall back to an idempotent no-op is impossible
    # (there is nothing to return) → surface it as a 409-style conflict via the router.
    request = _create_request(submission, counterparty_name, policy_number)
    policy_ref = policy_client.create_policy(request)
    policy_client.submit(policy_ref.id)
    policy_client.activate(policy_ref.id)

    event = {
        "policy_number": policy_number,
        "submission_id": submission.id,
        "quote_id": quote.id,
        "premium_minor": quote.premium_minor,
        "currency": quote.currency,
        "product_code": request.product_code,
        "effective_date": request.effective_date,
        "expiry_date": request.expiry_date,
    }

    # Publish is best-effort: a failure must NOT fail an already-activated bind — log + record it in
    # the audit detail and leave event_published False.
    event_published = _publish_best_effort(publisher, event)

    binding = bindings.add(
        submission_id=submission.id,
        quote_id=quote.id,
        policy_number=policy_number,
        pas_policy_id=policy_ref.id,
        status="bound",
        event_published=event_published,
        bound_by=actor,
    )
    audit.append(
        submission_id=submission.id,
        action="bind",
        actor=actor,
        detail={
            "policy_number": policy_number,
            "pas_policy_id": policy_ref.id,
            "quote_id": quote.id,
            "premium_minor": quote.premium_minor,
            "currency": quote.currency,
            "event_published": event_published,
        },
    )
    session.commit()
    session.refresh(binding)
    return binding


def _counterparty_name(session: Session, submission: Submission) -> str:
    """The policy holder name = the submission's counterparty name (local entity model, ADR-002)."""
    from app.entity.models import Counterparty

    counterparty = session.get(Counterparty, submission.counterparty_id)
    return counterparty.name if counterparty is not None else submission.counterparty_id


def _publish_best_effort(publisher: BoundRiskPublisher, event: dict) -> bool:
    try:
        publisher.publish(event)
        return True
    except Exception as exc:  # best-effort — never fail the bind on a publish error
        logger.warning("bound-risk publish failed for %s: %s", event.get("policy_number"), exc)
        return False


def latest_binding(session: Session, submission_id: str, bindings: BindingRepository) -> Binding | None:
    return bindings.by_submission(submission_id)


# Re-exported so the router can map the client-level conflict without importing the client module.
__all__ = [
    "NoAcceptedDecisionError",
    "NoQuoteError",
    "PolicyAlreadyExistsError",
    "bind_submission",
    "latest_binding",
    "policy_number_for",
]
