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


# --- POST /v1/submissions/{id}/quote ---------------------------------------


def test_quote_accept_returns_premium_and_breakdown(client: TestClient) -> None:
    sub_id = _create(client)  # warehouse €500,000 FR → accept
    assert client.post(f"/v1/submissions/{sub_id}/assess").json()["outcome"] == "accept"
    resp = client.post(f"/v1/submissions/{sub_id}/quote")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # warehouse factor 1.25: 0.5‰ × €500,000 × 1.25 = €312.50 = 31_250 eurocents
    assert body["premium_minor"] == 31_250
    assert body["currency"] == "EUR"
    assert body["rate_table_version"] == 1
    assert body["submission_id"] == sub_id
    kinds = [li["kind"] for li in body["breakdown"]]
    assert kinds == ["base", "factor"]
    # breakdown reconciles to the premium
    assert body["breakdown"][-1]["running_subtotal_minor"] == body["premium_minor"]


def test_quote_refer_is_allowed(client: TestClient) -> None:
    # above authority → refer (not decline) → quotable
    sub_id = _create(client, tiv_eur=2_000_000_000)
    assert client.post(f"/v1/submissions/{sub_id}/assess").json()["outcome"] == "refer"
    resp = client.post(f"/v1/submissions/{sub_id}/quote")
    assert resp.status_code == 200, resp.text
    assert resp.json()["premium_minor"] > 0


def test_quote_declined_risk_409(client: TestClient) -> None:
    sub_id = _create(client, country="KP")  # sanctioned → decline
    assert client.post(f"/v1/submissions/{sub_id}/assess").json()["outcome"] == "decline"
    resp = client.post(f"/v1/submissions/{sub_id}/quote")
    assert resp.status_code == 409


def test_quote_without_decision_404(client: TestClient) -> None:
    sub_id = _create(client)  # never assessed
    resp = client.post(f"/v1/submissions/{sub_id}/quote")
    assert resp.status_code == 404


def test_quote_missing_submission_404(client: TestClient) -> None:
    resp = client.post("/v1/submissions/nope/quote")
    assert resp.status_code == 404


def test_quote_writes_audit_entry(client: TestClient) -> None:
    sub_id = _create(client)
    client.post(f"/v1/submissions/{sub_id}/assess")
    client.post(f"/v1/submissions/{sub_id}/quote")
    actions = [e["action"] for e in client.get(f"/v1/submissions/{sub_id}/audit").json()]
    assert actions == ["submission.created", "submission.assessed", "quote"]


def test_requote_yields_new_latest_quote(client: TestClient) -> None:
    sub_id = _create(client)
    client.post(f"/v1/submissions/{sub_id}/assess")
    first = client.post(f"/v1/submissions/{sub_id}/quote").json()
    second = client.post(f"/v1/submissions/{sub_id}/quote").json()
    assert first["id"] != second["id"]
    latest = client.get(f"/v1/submissions/{sub_id}/quote").json()
    assert latest["id"] == second["id"]


# --- GET /v1/submissions/{id}/quote ----------------------------------------


def test_get_quote_before_quoting_404(client: TestClient) -> None:
    sub_id = _create(client)
    resp = client.get(f"/v1/submissions/{sub_id}/quote")
    assert resp.status_code == 404


def test_get_quote_missing_submission_404(client: TestClient) -> None:
    resp = client.get("/v1/submissions/nope/quote")
    assert resp.status_code == 404


# --- GET /v1/rate-tables ----------------------------------------------------


def test_list_rate_tables(client: TestClient) -> None:
    resp = client.get("/v1/rate-tables")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["version"] == 1
    assert "base_rate_permille" in body[0]["rules"]


# --- GET /v1/submissions (inbox) -------------------------------------------


def test_list_empty(client: TestClient) -> None:
    resp = client.get("/v1/submissions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_newest_first_with_outcome_and_bound_flags(client: TestClient) -> None:
    first = _create(client)  # unassessed
    second = _create(client, tiv_eur=2_000_000_000)  # will be referred
    client.post(f"/v1/submissions/{second}/assess")

    body = client.get("/v1/submissions").json()
    assert [item["id"] for item in body] == [second, first]  # newest first
    by_id = {item["id"]: item for item in body}
    assert by_id[first]["latest_outcome"] is None and by_id[first]["bound"] is False
    assert by_id[second]["latest_outcome"] == "refer" and by_id[second]["bound"] is False


def test_list_filters_by_latest_outcome(client: TestClient) -> None:
    accepted = _create(client)
    client.post(f"/v1/submissions/{accepted}/assess")  # accept
    referred = _create(client, tiv_eur=2_000_000_000)
    client.post(f"/v1/submissions/{referred}/assess")  # refer
    _create(client)  # unassessed → excluded by any outcome filter

    refers = client.get("/v1/submissions", params={"outcome": "refer"}).json()
    assert [item["id"] for item in refers] == [referred]
    accepts = client.get("/v1/submissions", params={"outcome": "accept"}).json()
    assert [item["id"] for item in accepts] == [accepted]


def test_list_filter_rejects_bad_outcome_422(client: TestClient) -> None:
    resp = client.get("/v1/submissions", params={"outcome": "not-a-real-outcome"})
    assert resp.status_code == 422


def test_list_pagination_limit(client: TestClient) -> None:
    for _ in range(3):
        _create(client)
    resp = client.get("/v1/submissions", params={"limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    # limit is bounded (1..200)
    assert client.get("/v1/submissions", params={"limit": 0}).status_code == 422


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
