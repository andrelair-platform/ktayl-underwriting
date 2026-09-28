"""API-level auth tests: with AUTHENTIK_JWKS_URL set, /v1 routes enforce bearer + scope, and the
authenticated actor (not the dev placeholder) is recorded in decisions/bindings/audit. No network —
the JWKS transport is faked; the RS256 signature check is real.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.auth as auth
from app.api.deps import get_bound_risk_publisher, get_policy_service_client, get_token_provider
from app.config import get_settings
from app.db.base import get_db
from tests.fixtures.auth import FakePyJWKClient, make_token
from tests.fixtures.bind import FakeBoundRiskPublisher, FakePolicyServiceClient, FakeTokenProvider
from tests.fixtures.submissions import submission_payload


@pytest.fixture
def auth_client(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Turn auth ON on the cached settings + fake the JWKS client (no HTTP).
    monkeypatch.setattr(get_settings(), "authentik_jwks_url", "https://auth.example/jwks")
    monkeypatch.setattr(auth, "_jwks_client", lambda url: FakePyJWKClient(url))

    from app.main import create_app

    app = create_app()

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_policy_service_client] = FakePolicyServiceClient
    app.dependency_overrides[get_bound_risk_publisher] = FakeBoundRiskPublisher
    app.dependency_overrides[get_token_provider] = FakeTokenProvider
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- 401 / 403 / 200 --------------------------------------------------------


def test_no_token_401(auth_client: TestClient) -> None:
    assert auth_client.post("/v1/submissions", json=submission_payload()).status_code == 401


def test_read_with_write_only_scope_403(auth_client: TestClient) -> None:
    token = make_token(scope="underwriting:write")  # lacks :read
    assert auth_client.get("/v1/rate-tables", headers=_bearer(token)).status_code == 403


def test_write_with_read_only_scope_403(auth_client: TestClient) -> None:
    token = make_token(scope="underwriting:read")  # lacks :write
    resp = auth_client.post("/v1/submissions", json=submission_payload(), headers=_bearer(token))
    assert resp.status_code == 403


def test_expired_token_401(auth_client: TestClient) -> None:
    token = make_token(expired=True)
    assert auth_client.get("/v1/rate-tables", headers=_bearer(token)).status_code == 401


def test_read_with_right_scope_200(auth_client: TestClient) -> None:
    token = make_token(scope="underwriting:read")
    assert auth_client.get("/v1/rate-tables", headers=_bearer(token)).status_code == 200


def test_ops_endpoints_stay_unauthenticated(auth_client: TestClient) -> None:
    assert auth_client.get("/healthz").status_code == 200
    assert auth_client.get("/info").status_code == 200


# --- actor propagation (auth ON records the token actor, not the placeholder) -------------------


def test_decision_records_token_actor(auth_client: TestClient) -> None:
    token = make_token(scope="underwriting:read underwriting:write", preferred_username="dave@ktayl")
    sub_id = auth_client.post("/v1/submissions", json=submission_payload(), headers=_bearer(token)).json()["id"]
    decision = auth_client.post(f"/v1/submissions/{sub_id}/assess", headers=_bearer(token)).json()
    assert decision["decided_by"] == "dave@ktayl"
    # the audit trail also carries the real actor, never the dev placeholder
    audit = auth_client.get(f"/v1/submissions/{sub_id}/audit", headers=_bearer(token)).json()
    actors = {e["actor"] for e in audit}
    assert actors == {"dave@ktayl"}
    assert "underwriter@ktayl" not in actors


def test_binding_records_token_actor(auth_client: TestClient) -> None:
    token = make_token(scope="underwriting:read underwriting:write", preferred_username="erin@ktayl")
    h = _bearer(token)
    sub_id = auth_client.post("/v1/submissions", json=submission_payload(), headers=h).json()["id"]
    auth_client.post(f"/v1/submissions/{sub_id}/assess", headers=h)
    auth_client.post(f"/v1/submissions/{sub_id}/quote", headers=h)
    binding = auth_client.post(f"/v1/submissions/{sub_id}/bind", headers=h).json()
    assert binding["bound_by"] == "erin@ktayl"
