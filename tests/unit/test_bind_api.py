"""API tests for POST/GET /v1/submissions/{id}/bind over SQLite in-memory, with the three bind
seams (PolicyServiceClient / BoundRiskPublisher / TokenProvider) overridden — no httpx/NATS.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_bound_risk_publisher, get_policy_service_client, get_token_provider
from app.db.base import get_db
from tests.fixtures.bind import FakeBoundRiskPublisher, FakePolicyServiceClient, FakeTokenProvider
from tests.fixtures.submissions import submission_payload


@pytest.fixture
def fake_policy_client() -> FakePolicyServiceClient:
    return FakePolicyServiceClient()


@pytest.fixture
def fake_publisher() -> FakeBoundRiskPublisher:
    return FakeBoundRiskPublisher()


@pytest.fixture
def bind_client(
    db_session: Session,
    fake_policy_client: FakePolicyServiceClient,
    fake_publisher: FakeBoundRiskPublisher,
) -> Iterator[TestClient]:
    from app.main import create_app

    app = create_app()

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_policy_service_client] = lambda: fake_policy_client
    app.dependency_overrides[get_bound_risk_publisher] = lambda: fake_publisher
    app.dependency_overrides[get_token_provider] = lambda: FakeTokenProvider()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_assess_quote(client: TestClient, **overrides: object) -> str:
    resp = client.post("/v1/submissions", json=submission_payload(**overrides))
    assert resp.status_code == 201, resp.text
    sub_id = resp.json()["id"]
    assert client.post(f"/v1/submissions/{sub_id}/assess").json()["outcome"] == "accept"
    assert client.post(f"/v1/submissions/{sub_id}/quote").status_code == 200
    return sub_id


# --- happy path -------------------------------------------------------------


def test_bind_happy(
    bind_client: TestClient,
    fake_policy_client: FakePolicyServiceClient,
    fake_publisher: FakeBoundRiskPublisher,
) -> None:
    sub_id = _create_assess_quote(bind_client)
    resp = bind_client.post(f"/v1/submissions/{sub_id}/bind")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "bound"
    assert body["submission_id"] == sub_id
    assert body["policy_number"].startswith("UW-")
    assert body["event_published"] is True
    # the seams were actually exercised
    assert len(fake_policy_client.created) == 1
    assert len(fake_publisher.published) == 1
    # audit trail now ends with bind
    actions = [e["action"] for e in bind_client.get(f"/v1/submissions/{sub_id}/audit").json()]
    assert actions == ["submission.created", "submission.assessed", "quote", "bind"]


def test_bind_is_idempotent_over_api(
    bind_client: TestClient,
    fake_policy_client: FakePolicyServiceClient,
    fake_publisher: FakeBoundRiskPublisher,
) -> None:
    sub_id = _create_assess_quote(bind_client)
    first = bind_client.post(f"/v1/submissions/{sub_id}/bind").json()
    second = bind_client.post(f"/v1/submissions/{sub_id}/bind").json()
    assert first["id"] == second["id"]
    assert len(fake_policy_client.created) == 1
    assert len(fake_publisher.published) == 1


# --- guard failures ---------------------------------------------------------


def test_bind_without_quote_422(bind_client: TestClient) -> None:
    resp = bind_client.post("/v1/submissions", json=submission_payload())
    sub_id = resp.json()["id"]
    bind_client.post(f"/v1/submissions/{sub_id}/assess")  # accepted, but never quoted
    resp = bind_client.post(f"/v1/submissions/{sub_id}/bind")
    assert resp.status_code == 422


def test_bind_non_accept_422(bind_client: TestClient) -> None:
    # above authority → refer (quotable, but not bindable in v1)
    resp = bind_client.post("/v1/submissions", json=submission_payload(tiv_eur=2_000_000_000))
    sub_id = resp.json()["id"]
    assert bind_client.post(f"/v1/submissions/{sub_id}/assess").json()["outcome"] == "refer"
    bind_client.post(f"/v1/submissions/{sub_id}/quote")
    resp = bind_client.post(f"/v1/submissions/{sub_id}/bind")
    assert resp.status_code == 422


def test_bind_missing_submission_404(bind_client: TestClient) -> None:
    resp = bind_client.post("/v1/submissions/nope/bind")
    assert resp.status_code == 404


# --- GET /v1/submissions/{id}/bind -----------------------------------------


def test_get_binding_before_bind_404(bind_client: TestClient) -> None:
    sub_id = _create_assess_quote(bind_client)
    assert bind_client.get(f"/v1/submissions/{sub_id}/bind").status_code == 404


def test_get_binding_after_bind(bind_client: TestClient) -> None:
    sub_id = _create_assess_quote(bind_client)
    bind_client.post(f"/v1/submissions/{sub_id}/bind")
    resp = bind_client.get(f"/v1/submissions/{sub_id}/bind")
    assert resp.status_code == 200
    assert resp.json()["submission_id"] == sub_id


def test_get_binding_missing_submission_404(bind_client: TestClient) -> None:
    assert bind_client.get("/v1/submissions/nope/bind").status_code == 404
