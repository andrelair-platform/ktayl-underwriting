"""L3 contract test — the payload this service POSTs to ktayl-policy-service.

THE key test of the whole suite. The bind flow's external boundary (the policy service) is *mocked* in
L1; this layer is what keeps that mock honest. It validates the exact ``CreatePolicyRequest`` body the
app produces against the sibling service's **vendored OpenAPI** contract, with a jsonschema
**format checker enabled** so ``format: date-time`` is genuinely enforced.

The regression this exists for (see ``app/bind/service.py::_cover_dates``): the policy-service Go
validator requires a full RFC3339 **datetime** for ``effective_date`` / ``expiry_date``; a bare date
(``2026-09-27``) is rejected at runtime. A unit test with a fake client can't catch that — only
validating against the real contract can. The ``test_..._bare_date_fails_validation`` guard proves this
layer catches exactly that bug.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

from app.bind.service import _create_request
from app.submission.models import Submission

_SPEC_PATH = Path(__file__).parent / "policy_service_openapi.yaml"


@pytest.fixture(scope="module")
def spec() -> dict[str, Any]:
    """The vendored ktayl-policy-service OpenAPI spec (the contract source of truth)."""
    return yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def create_policy_schema(spec: dict[str, Any]) -> dict[str, Any]:
    """The ``CreatePolicyRequest`` request-body schema, resolved from the spec components.

    Injects ``components`` so any internal ``$ref`` still resolves (jsonschema's RefResolver walks it).
    """
    schema = spec["components"]["schemas"]["CreatePolicyRequest"]
    return {**schema, "components": spec["components"]}


def _validator(schema: dict[str, Any]) -> jsonschema.Draft7Validator:
    """A Draft-7 validator with the FORMAT checker enabled — this is what makes ``format: date-time``
    actually enforced (jsonschema ignores ``format`` unless a format_checker is passed)."""
    return jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())


def _app_request_payload() -> dict[str, Any]:
    """The exact dict the app posts: build a submission → run the real request mapper → the JSON body.

    Mirrors ``HttpPolicyServiceClient.create_policy``'s ``json=`` body field-for-field (both are built
    from the same ``CreatePolicyRequest`` dataclass), so validating this dict validates what goes over
    the wire.
    """
    submission = Submission(
        counterparty_id="cp-1",
        line_of_business="commercial_property",
        tiv_eur=500_000_00,
        occupancy="warehouse",
        country="FR",
        postcode="75001",
        requested_cover="All-risks property damage + business interruption",
        broker_ref="BRK-001",
    )
    req = _create_request(submission, counterparty_name="Acme Logistics SAS", policy_number="UW-ABC123DEF456")
    return asdict(req)


def test_app_create_request_satisfies_policy_service_contract(create_policy_schema: dict[str, Any]) -> None:
    """The request the app actually sends PASSES the vendored CreatePolicyRequest contract."""
    payload = _app_request_payload()
    # Sanity: the dates the app builds are full RFC3339 datetimes (what the Go validator requires).
    assert payload["effective_date"].endswith("Z")
    assert "T" in payload["effective_date"]

    errors = sorted(_validator(create_policy_schema).iter_errors(payload), key=str)
    assert errors == [], f"app request violates the policy-service contract: {[e.message for e in errors]}"


def test_bare_date_fails_validation(create_policy_schema: dict[str, Any]) -> None:
    """GUARD: a bare-date payload (``2026-09-27``) MUST fail validation.

    This is the exact RFC3339 regression this contract layer exists to catch — the policy-service
    requires ``format: date-time`` (a full datetime), so a bare ``date`` is a contract violation. If
    this ever passes, the layer has gone blind to the bug it was built to guard.
    """
    payload = _app_request_payload()
    payload["effective_date"] = "2026-09-27"  # a bare date — NOT a valid date-time

    errors = list(_validator(create_policy_schema).iter_errors(payload))
    assert errors, "bare date must NOT satisfy format: date-time — the contract check has gone blind"
    # The failure is specifically about the effective_date / date-time format.
    assert any("effective_date" in list(e.absolute_path) or "date-time" in e.message for e in errors), (
        f"expected a date-time format failure, got: {[e.message for e in errors]}"
    )


def test_required_fields_enforced(create_policy_schema: dict[str, Any]) -> None:
    """A payload missing a required field (policy_number) fails — the contract requires all five."""
    payload = _app_request_payload()
    del payload["policy_number"]
    errors = list(_validator(create_policy_schema).iter_errors(payload))
    assert errors, "a payload missing policy_number must fail the contract"


def test_lifecycle_paths_exist_in_spec(spec: dict[str, Any]) -> None:
    """The lifecycle endpoints HttpPolicyServiceClient calls exist as paths in the contract.

    The client hits POST /v1/policies then POST /v1/policies/{id}/{submit,activate}. The submit/activate
    sub-paths are not separate OpenAPI paths in the thin v1 spec, but the collection + item paths the
    id-resolving flow relies on must exist.
    """
    paths = spec["paths"]
    assert "/v1/policies" in paths, "POST/GET /v1/policies (create + resolve-existing) missing from spec"
    assert "post" in paths["/v1/policies"], "POST /v1/policies (create) missing from spec"
    assert "get" in paths["/v1/policies"], "GET /v1/policies (409 resolve-existing) missing from spec"
    assert "/v1/policies/{id}" in paths, "GET /v1/policies/{id} (policy item) missing from spec"
