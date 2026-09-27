"""Unit tests for the bind module — pure policy_number + orchestration with fakes (no network).

The orchestration is driven against the same in-memory SQLite session the API tests use, but with
fake PolicyServiceClient / BoundRiskPublisher / TokenProvider so L1 makes no httpx/NATS calls.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.audit.repository import SqlAuditRepository
from app.bind import service as bind_service
from app.bind.repository import SqlBindingRepository
from app.bind.service import policy_number_for
from app.decision.models import Decision
from app.entity.models import Counterparty
from app.rating.models import Quote
from app.rating.repository import SqlQuoteRepository
from app.submission import service as submission_service
from app.submission.models import Submission
from tests.fixtures.bind import FakeBoundRiskPublisher, FakePolicyServiceClient, FakeTokenProvider

_ACTOR = "underwriter@test"


# --- deterministic policy_number -------------------------------------------


def test_policy_number_is_deterministic() -> None:
    assert policy_number_for("quote-123") == policy_number_for("quote-123")


def test_policy_number_differs_per_quote() -> None:
    assert policy_number_for("quote-a") != policy_number_for("quote-b")


def test_policy_number_shape() -> None:
    number = policy_number_for("quote-123")
    assert number.startswith("UW-")
    assert len(number) == len("UW-") + 12
    assert number[3:].isalnum() and number[3:].isupper()


# --- orchestration helpers --------------------------------------------------


def _seed(session: Session, *, outcome: str = "accept", with_quote: bool = True) -> str:
    """Insert a counterparty + submission + a decision (+ optional quote); return the submission id."""
    cp = Counterparty(name="Acme Logistics SAS", country="FR")
    session.add(cp)
    session.flush()
    submission = Submission(
        counterparty_id=cp.id,
        line_of_business="commercial_property",
        tiv_eur=500_000_00,
        occupancy="warehouse",
        country="FR",
        postcode="75001",
        requested_cover="All-risks property damage",
        broker_ref="BRK-001",
    )
    session.add(submission)
    session.flush()
    session.add(
        Decision(
            submission_id=submission.id,
            outcome=outcome,
            reason_codes=["WITHIN_APPETITE"],
            appetite_version=1,
            decided_by=_ACTOR,
        )
    )
    if with_quote:
        session.add(
            Quote(
                submission_id=submission.id,
                premium_minor=31_250,
                currency="EUR",
                rate_table_version=1,
                breakdown=[],
                created_by=_ACTOR,
            )
        )
    session.commit()
    return submission.id


def _bind(
    session: Session,
    submission_id: str,
    client: FakePolicyServiceClient,
    publisher: FakeBoundRiskPublisher,
):
    return bind_service.bind_submission(
        session,
        submission_id,
        SqlBindingRepository(session),
        SqlQuoteRepository(session),
        SqlAuditRepository(session),
        client,
        publisher,
        actor=_ACTOR,
    )


# --- happy path -------------------------------------------------------------


def test_bind_happy_creates_submits_activates_records_and_publishes(db_session: Session) -> None:
    sub_id = _seed(db_session)
    client = FakePolicyServiceClient()
    publisher = FakeBoundRiskPublisher()

    binding = _bind(db_session, sub_id, client, publisher)

    # create → submit → activate, exactly once each, on the same PAS id
    assert len(client.created) == 1
    assert client.submitted == [binding.pas_policy_id]
    assert client.activated == [binding.pas_policy_id]
    # binding recorded
    assert binding.status == "bound"
    assert binding.policy_number.startswith("UW-")
    assert binding.event_published is True
    # event published with the right shape + subject-bound fields
    assert len(publisher.published) == 1
    event = publisher.published[0]
    assert event["policy_number"] == binding.policy_number
    assert event["submission_id"] == sub_id
    assert event["premium_minor"] == 31_250
    assert event["currency"] == "EUR"
    assert event["product_code"] == "COMM_PROP"
    assert set(event) == {
        "policy_number",
        "submission_id",
        "quote_id",
        "premium_minor",
        "currency",
        "product_code",
        "effective_date",
        "expiry_date",
    }
    # audit entry written
    actions = [e.action for e in SqlAuditRepository(db_session).list_for_submission(sub_id)]
    assert "bind" in actions


def test_bind_create_request_maps_holder_and_product(db_session: Session) -> None:
    sub_id = _seed(db_session)
    client = FakePolicyServiceClient()
    _bind(db_session, sub_id, client, FakeBoundRiskPublisher())
    request = client.created[0]
    assert request.holder_name == "Acme Logistics SAS"
    assert request.product_code == "COMM_PROP"
    # default cover period: effective today, expiry +1y (a sensible v1 default)
    assert request.effective_date < request.expiry_date


# --- 409-on-create → treated as success (idempotent) ------------------------


def test_bind_create_conflict_is_treated_as_success(db_session: Session) -> None:
    sub_id = _seed(db_session)
    client = FakePolicyServiceClient(conflict_on_create=True, existing_id="pas-existing-1")
    publisher = FakeBoundRiskPublisher()

    binding = _bind(db_session, sub_id, client, publisher)

    # the resolved existing id is used for submit/activate + recorded
    assert binding.pas_policy_id == "pas-existing-1"
    assert client.submitted == ["pas-existing-1"]
    assert client.activated == ["pas-existing-1"]
    assert len(publisher.published) == 1


def test_bind_create_conflict_unresolvable_raises(db_session: Session) -> None:
    sub_id = _seed(db_session)
    client = FakePolicyServiceClient(conflict_on_create=True, existing_id=None)
    with pytest.raises(bind_service.PolicyAlreadyExistsError):
        _bind(db_session, sub_id, client, FakeBoundRiskPublisher())


# --- guard paths ------------------------------------------------------------


def test_bind_rejects_non_accept_decision(db_session: Session) -> None:
    sub_id = _seed(db_session, outcome="refer")
    client = FakePolicyServiceClient()
    with pytest.raises(bind_service.NoAcceptedDecisionError):
        _bind(db_session, sub_id, client, FakeBoundRiskPublisher())
    assert client.created == []  # no PAS calls on a rejected guard


def test_bind_rejects_when_no_quote(db_session: Session) -> None:
    sub_id = _seed(db_session, with_quote=False)
    client = FakePolicyServiceClient()
    with pytest.raises(bind_service.NoQuoteError):
        _bind(db_session, sub_id, client, FakeBoundRiskPublisher())
    assert client.created == []


def test_bind_missing_submission_raises(db_session: Session) -> None:
    client = FakePolicyServiceClient()
    with pytest.raises(submission_service.SubmissionNotFoundError):
        _bind(db_session, "does-not-exist", client, FakeBoundRiskPublisher())


# --- idempotent re-bind → no second set of PAS calls, no duplicate event ----


def test_rebind_is_idempotent_no_op(db_session: Session) -> None:
    sub_id = _seed(db_session)
    client = FakePolicyServiceClient()
    publisher = FakeBoundRiskPublisher()

    first = _bind(db_session, sub_id, client, publisher)
    second = _bind(db_session, sub_id, client, publisher)

    assert first.id == second.id
    # exactly ONE set of PAS calls + ONE event, despite two bind requests
    assert len(client.created) == 1
    assert len(client.submitted) == 1
    assert len(client.activated) == 1
    assert len(publisher.published) == 1


# --- best-effort publish ----------------------------------------------------


def test_bind_survives_publish_failure(db_session: Session) -> None:
    sub_id = _seed(db_session)
    client = FakePolicyServiceClient()
    publisher = FakeBoundRiskPublisher(fail=True)

    binding = _bind(db_session, sub_id, client, publisher)

    # bind succeeded (activate ran) even though publish failed; event_published recorded False
    assert client.activated == [binding.pas_policy_id]
    assert binding.event_published is False
    assert publisher.published == []
    detail = SqlAuditRepository(db_session).list_for_submission(sub_id)[-1].detail
    assert detail["event_published"] is False


# --- token provider seam ----------------------------------------------------


def test_token_provider_is_a_seam() -> None:
    provider = FakeTokenProvider("abc")
    assert provider.token() == "abc"
    assert provider.calls == 1
