"""In-memory fakes for the bind external seams — no httpx/NATS in L1.

These implement the ``PolicyServiceClient`` / ``BoundRiskPublisher`` / ``TokenProvider`` protocols
structurally, record their calls, and let a test simulate a 409-on-create.
"""

from __future__ import annotations

from app.bind.policy_client import CreatePolicyRequest, PolicyAlreadyExistsError, PolicyRef


class FakePolicyServiceClient:
    """Records the create→submit→activate calls; can simulate 409-on-create (idempotency)."""

    def __init__(self, *, conflict_on_create: bool = False, existing_id: str | None = None) -> None:
        # conflict_on_create → the deterministic policy_number already exists in the PAS.
        # existing_id: the id resolved on a 409 (None → PolicyAlreadyExistsError, mirroring an
        # unresolvable existing policy).
        self._conflict_on_create = conflict_on_create
        self._existing_id = existing_id
        self.created: list[CreatePolicyRequest] = []
        self.submitted: list[str] = []
        self.activated: list[str] = []

    def create_policy(self, req: CreatePolicyRequest) -> PolicyRef:
        self.created.append(req)
        if self._conflict_on_create:
            if self._existing_id is None:
                raise PolicyAlreadyExistsError(req.policy_number)
            return PolicyRef(id=self._existing_id, status="draft")
        return PolicyRef(id=f"pas-{req.policy_number}", status="draft")

    def submit(self, policy_id: str) -> None:
        self.submitted.append(policy_id)

    def activate(self, policy_id: str) -> None:
        self.activated.append(policy_id)


class FakeBoundRiskPublisher:
    """Records published events; ``fail`` makes publish raise (best-effort path)."""

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.published: list[dict] = []

    def publish(self, event: dict) -> None:
        if self._fail:
            raise RuntimeError("nats unavailable")
        self.published.append(event)


class FakeTokenProvider:
    """A static token provider — asserts the seam is injected, no network."""

    def __init__(self, value: str = "test-token") -> None:
        self._value = value
        self.calls = 0

    def token(self) -> str:
        self.calls += 1
        return self._value
