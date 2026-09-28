# Contract tests (L3)

These tests pin the **contracts** this service depends on — no Docker, no network, fast enough to run
on every push.

## `policy_service_openapi.yaml` — a VENDORED copy

`policy_service_openapi.yaml` is a **committed, vendored copy** of the sibling repo's API spec:
`ktayl-policy-service/api/openapi.yaml`. It is the contract source of truth for the payload this
service POSTs to the policy service when binding a risk (`create → submit → activate`).

Vendoring (rather than reading the sibling repo at test time) is deliberate: the contract test must be
self-contained and reproducible in CI, where the sibling repo is not checked out. The copy is the
frozen version of the contract this service was built against.

### Refreshing the copy

When the policy service's API changes, refresh this file from the sibling repo:

```bash
cp ../ktayl-policy-service/api/openapi.yaml tests/contract/policy_service_openapi.yaml
```

Then run `pytest tests/contract -q`. If the contract test now fails, the policy-service contract
changed in a way that breaks the request this service sends (e.g. a newly required field, or a
tightened `format`) — fix `app/bind/` to match, then commit the refreshed spec + the fix together.

## Tests

- **`test_policy_service_contract.py`** — the key test. It loads the vendored spec, extracts the
  `CreatePolicyRequest` schema, and validates the dict this app actually sends (built via
  `app.bind.service._create_request`) against it with a **format checker enabled**, so
  `format: date-time` is genuinely enforced. It asserts the current request PASSES, and includes a
  guard proving a bare-date payload FAILS (the exact RFC3339 regression this layer exists to catch).
  It also asserts the lifecycle paths the client calls exist in the spec.
- **`test_openapi_self.py`** — validates this service's OWN OpenAPI (`app.openapi()`) and runs a small,
  fast, deterministic schemathesis pass over the read/ops endpoints.
