---
id: UW-01-S02
title: "Bind: hand a quoted risk to the live policy service + emit bound-risk event (ADR-006)"
status: Ready
type: Story
epic: underwriting
milestone: "UW — Underwriting v1"
estimate: 5
labels: [insurance-lob, underwriting, backend, python, integration]
priority: P1
assignee: AndreLiar
repo: andrelair-platform/ktayl-underwriting
project: 12
initiative: Insurance LOB
---

*As an* **underwriter**, *I want* to **bind** an accepted + quoted risk into the live `ktayl-policy-service`
and emit a bound-risk event *so that* the risk becomes an active policy and downstream (reinsurance/
actuarial) is notified — the final step of the workbench (UW-01), after appetite (S01) + rating (UW-04).

## Contract (ADR-006 — bind against the LIVE policy service as-is, no change to it)
The live PAS lifecycle (`ktayl-policy-service` `internal/api/router.go`, OIDC scope `policy:write`):
1. `POST /v1/policies` → `{policy_number, holder_name, product_code, effective_date, expiry_date}` → `draft`
2. `POST /v1/policies/{id}/submit` → draft → submitted
3. `POST /v1/policies/{id}/activate` → submitted → **active** (this is "bind")

## Scope (this slice)
- **`bind` module** orchestrating the 3-step lifecycle, behind interfaces so it's unit-testable with mocks:
  - a **`PolicyServiceClient`** interface (httpx impl) — create → submit → activate;
  - a **`BoundRiskPublisher`** interface (NATS impl) — publish the bound-risk event.
- **Idempotency (ADR-006):** derive a **deterministic `policy_number`** from the UW quote id (stable hash),
  so a retry is a no-op — PAS returns `409` on a duplicate create → treat as **success** (fetch/So proceed).
- **Bound-risk event** on NATS after activate: `{policy_number, submission_id, quote_id, premium_minor,
  currency, product_code, effective_date, expiry_date}` — the seam for reinsurance/actuarial.
- **UW-side binding record** (a `Binding`: submission_id, quote_id, policy_number, pas_policy_id, status,
  bound_at) — premium/terms stay in the UW record linked by `policy_number` (ADR-006 accepted limitation:
  the thin PAS `CreatePolicyRequest` carries no premium/terms yet).
- **Auth:** the UW service calls PAS with an OIDC **client-credentials** token (scope `policy:write`),
  behind a `TokenProvider` interface (mocked in tests; real impl = Authentik client_credentials).
- **Audit** entry on bind.

## Endpoint
- `POST /v1/submissions/{id}/bind` → **guard:** latest decision must be `accept` **and** a quote must exist
  (else `409`/`422`); `404` if missing. Runs create→submit→activate (idempotent), records the Binding,
  publishes the event, returns the binding. Re-bind of an already-bound submission = idempotent no-op (returns the existing binding).

## Out of scope (follow-on)
- Binding a `refer` risk (needs committee UW-03), extending the PAS `CreatePolicyRequest` with premium/terms
  (a policy-service change — ADR-006 follow-up), retries/backoff tuning beyond basic, the UI.

## Acceptance criteria
- Deterministic `policy_number(quote_id)` is pure + tested (same quote → same number).
- Orchestration tested with a **mocked** PolicyServiceClient + publisher: happy path (create→submit→activate
  → binding recorded + event published + audit); **409-on-create → treated as success** (idempotent);
  guard paths (no accept / no quote → rejected); re-bind → no duplicate.
- No real network in L1 (interfaces mocked); L0 ruff+mypy green; L1 pytest ≥70%.
- Same modular-monolith shape as S01/UW-04; the PAS client, publisher, and token provider are injected.

## Notes
- Stack per ADR-007. Deploy wiring (later, by me): Authentik client-credentials app (scope `policy:write`)
  → creds via Vault→ESO; `POLICY_SERVICE_URL` (dev PAS) + `NATS_URL` env; egress already open (Ingress-only
  netpols). The bound-risk event is what makes underwriting the authoritative premium source downstream.
