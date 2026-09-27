"""PolicyServiceClient — the seam over the live ``ktayl-policy-service`` (a separate Go service).

Binding is a **3-step lifecycle** against the live thin API (ADR-006), authenticated with an OIDC
JWT (scope ``policy:write``) from a ``TokenProvider``:
    1. ``POST /v1/policies``            → creates a ``draft`` policy (``409`` if policy_number exists)
    2. ``POST /v1/policies/{id}/submit``  → draft → submitted
    3. ``POST /v1/policies/{id}/activate``→ submitted → **active** (this is "bind")

Idempotency (ADR-006) rides on a **deterministic policy_number**: a duplicate create returns ``409``,
which the impl treats as **success** — it resolves the existing policy's id (via list/get) and returns
it so the caller can continue. If the id cannot be resolved, ``PolicyAlreadyExistsError`` is raised so
the orchestration can fall back to its own idempotent no-op keyed on the existing UW Binding row.

The interface is a ``typing.Protocol`` so tests inject a fake and L1 makes no network calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class CreatePolicyRequest:
    """The thin PAS create body (ADR-006: no premium/limits/terms yet)."""

    policy_number: str
    holder_name: str
    product_code: str
    effective_date: str  # ISO date (YYYY-MM-DD)
    expiry_date: str  # ISO date (YYYY-MM-DD)


@dataclass(frozen=True)
class PolicyRef:
    """A reference to a policy in the live PAS."""

    id: str
    status: str


class PolicyServiceError(Exception):
    """Raised on an unexpected policy-service response (non-2xx that is not a handled 409)."""


class PolicyAlreadyExistsError(Exception):
    """Raised when create returned 409 and the existing policy id could not be resolved.

    The orchestration treats this as an idempotent no-op keyed on the existing UW Binding row.
    """


class PolicyServiceClient(Protocol):
    """Drive the PAS policy lifecycle. ``create_policy`` returns the existing policy on a 409."""

    def create_policy(self, req: CreatePolicyRequest) -> PolicyRef: ...

    def submit(self, policy_id: str) -> None: ...

    def activate(self, policy_id: str) -> None: ...


class HttpPolicyServiceClient:
    """httpx-backed client against ``POLICY_SERVICE_URL``, bearer-authenticated per call."""

    def __init__(self, base_url: str, token_provider: TokenProviderLike, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token_provider = token_provider
        self._timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token_provider.token()}"}

    def create_policy(self, req: CreatePolicyRequest) -> PolicyRef:
        resp = httpx.post(
            f"{self._base_url}/v1/policies",
            json={
                "policy_number": req.policy_number,
                "holder_name": req.holder_name,
                "product_code": req.product_code,
                "effective_date": req.effective_date,
                "expiry_date": req.expiry_date,
            },
            headers=self._headers(),
            timeout=self._timeout_seconds,
        )
        if resp.status_code == httpx.codes.CREATED:
            body = resp.json()
            return PolicyRef(id=str(body["id"]), status=str(body.get("status", "draft")))
        if resp.status_code == httpx.codes.CONFLICT:
            # 409 → the policy already exists (deterministic policy_number). Treat as success: resolve
            # the existing id and continue (idempotent).
            existing = self._resolve_existing(req.policy_number)
            if existing is None:
                raise PolicyAlreadyExistsError(req.policy_number)
            return existing
        raise PolicyServiceError(f"create_policy → {resp.status_code}: {resp.text}")

    def _resolve_existing(self, policy_number: str) -> PolicyRef | None:
        """Look up an already-created policy by its (deterministic) policy_number."""
        resp = httpx.get(
            f"{self._base_url}/v1/policies",
            params={"policy_number": policy_number},
            headers=self._headers(),
            timeout=self._timeout_seconds,
        )
        if resp.status_code != httpx.codes.OK:
            return None
        body = resp.json()
        items = body if isinstance(body, list) else body.get("items", [])
        for item in items:
            if item.get("policy_number") == policy_number:
                return PolicyRef(id=str(item["id"]), status=str(item.get("status", "draft")))
        return None

    def submit(self, policy_id: str) -> None:
        self._transition(policy_id, "submit")

    def activate(self, policy_id: str) -> None:
        self._transition(policy_id, "activate")

    def _transition(self, policy_id: str, action: str) -> None:
        resp = httpx.post(
            f"{self._base_url}/v1/policies/{policy_id}/{action}",
            headers=self._headers(),
            timeout=self._timeout_seconds,
        )
        # A repeat transition on an already-advanced policy may 409; that is benign for an idempotent
        # re-bind, so only a hard failure raises.
        if resp.status_code not in (httpx.codes.OK, httpx.codes.CREATED, httpx.codes.CONFLICT):
            raise PolicyServiceError(f"{action} {policy_id} → {resp.status_code}: {resp.text}")


class TokenProviderLike(Protocol):
    """Minimal structural view of a token provider (avoids a hard import cycle)."""

    def token(self) -> str: ...
