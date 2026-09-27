"""API tests via FastAPI TestClient over a SQLite in-memory DB (no Docker/network).

Covers each endpoint: happy path + one failure path."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.fixtures.submissions import submission_payload


def _create(client: TestClient, **overrides: object) -> str:
    resp = client.post("/v1/submissions", json=submission_payload(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --- POST /v1/submissions ---------------------------------------------------


def test_create_submission_happy(client: TestClient) -> None:
    resp = client.post("/v1/submissions", json=submission_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["line_of_business"] == "commercial_property"
    assert body["tiv_eur"] == 500_000_00
    assert body["counterparty_id"]


def test_create_submission_validation_failure(client: TestClient) -> None:
    # tiv_eur must be > 0
    resp = client.post("/v1/submissions", json=submission_payload(tiv_eur=0))
    assert resp.status_code == 422


# --- POST /v1/submissions/{id}/assess --------------------------------------


def test_assess_accept(client: TestClient) -> None:
    sub_id = _create(client)
    resp = client.post(f"/v1/submissions/{sub_id}/assess")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == "accept"
    assert body["reason_codes"] == ["WITHIN_APPETITE"]
    assert body["appetite_version"] == 1
    assert body["submission_id"] == sub_id


def test_assess_refer_above_authority(client: TestClient) -> None:
    sub_id = _create(client, tiv_eur=2_000_000_000)
    resp = client.post(f"/v1/submissions/{sub_id}/assess")
    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "refer"
    assert body["reason_codes"] == ["TIV_ABOVE_AUTHORITY"]


def test_assess_decline_sanctioned(client: TestClient) -> None:
    sub_id = _create(client, country="KP")
    resp = client.post(f"/v1/submissions/{sub_id}/assess")
    assert resp.status_code == 200
    assert resp.json()["outcome"] == "decline"
    assert resp.json()["reason_codes"] == ["SANCTIONED_COUNTRY"]


def test_assess_missing_submission_404(client: TestClient) -> None:
    resp = client.post("/v1/submissions/does-not-exist/assess")
    assert resp.status_code == 404


# --- GET /v1/submissions/{id} ----------------------------------------------


def test_get_submission_includes_latest_decision(client: TestClient) -> None:
    sub_id = _create(client)
    client.post(f"/v1/submissions/{sub_id}/assess")
    resp = client.get(f"/v1/submissions/{sub_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == sub_id
    assert body["latest_decision"]["outcome"] == "accept"


def test_get_submission_before_assess_has_no_decision(client: TestClient) -> None:
    sub_id = _create(client)
    resp = client.get(f"/v1/submissions/{sub_id}")
    assert resp.status_code == 200
    assert resp.json()["latest_decision"] is None


def test_get_submission_missing_404(client: TestClient) -> None:
    resp = client.get("/v1/submissions/nope")
    assert resp.status_code == 404


# --- GET /v1/submissions/{id}/audit ----------------------------------------


def test_audit_log_is_append_only_trail(client: TestClient) -> None:
    sub_id = _create(client)
    client.post(f"/v1/submissions/{sub_id}/assess")
    resp = client.get(f"/v1/submissions/{sub_id}/audit")
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert actions == ["submission.created", "submission.assessed"]
    assessed = resp.json()[1]
    assert assessed["outcome"] == "accept"
    assert assessed["ruleset_version"] == 1


def test_audit_missing_submission_404(client: TestClient) -> None:
    resp = client.get("/v1/submissions/nope/audit")
    assert resp.status_code == 404


# --- ops endpoints ----------------------------------------------------------


def test_healthz(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_info(client: TestClient) -> None:
    resp = client.get("/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "ktayl-underwriting"
    assert body["version"]
